import json
from datetime import datetime, date
import pandas as pd
import os
from pathlib import Path

# Multi-user: API injects USER_DATA_DIR per user. Falls back to "data/" for manual runs.
DATA_DIR = Path(os.environ.get("USER_DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

SLEEP_PROFILE = str(DATA_DIR / "sleep_profile.json")
SLEEP_NIGHTLY = str(DATA_DIR / "sleep_index_nightly.csv")
CONSTRAINTS   = str(DATA_DIR / "tomorrow_constraints.json")
PLAN_OUT      = str(DATA_DIR / "tonight_plan.json")
NAP_LOG       = DATA_DIR / "nap_log.json"

TOP_K = 5
TARGET_MIN_DEFAULT = 480  # 8h

SOFT_WEIGHTS = {
    "late_bed_penalty_max":  0.35,
    "late_bed_window_min":   60,
    "caffeine_penalty_max":  0.20,
    "caffeine_window_min":   420,
}

# ── IO helpers ─────────────────────────────────────────────────────────────────

def load_json(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def minutes_from_midnight(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute

def fmt_time(mins: int) -> str:
    mins = int(mins) % 1440
    h = mins // 60
    m = mins % 60
    ampm = "AM" if h < 12 else "PM"
    h12  = h % 12
    if h12 == 0:
        h12 = 12
    return f"{h12}:{m:02d} {ampm}"

# ── Time math ──────────────────────────────────────────────────────────────────

def wrap_minutes(m: float) -> float:
    return (m - 720) % 1440

def circ_dist(a, b, period=1440):
    d = abs(a - b) % period
    return min(d, period - d)

def to_min_of_day(series_dt) -> pd.Series:
    dt = pd.to_datetime(series_dt, errors="coerce")
    return (dt.dt.hour * 60 + dt.dt.minute).astype("float")

def clamp_minute(x):
    if x is None:
        return None
    try:
        x = int(round(float(x)))
    except Exception:
        return None
    return max(0, min(1439, x))

# ── Constraints ────────────────────────────────────────────────────────────────

def normalize_constraints(constraints_in: dict, baseline: dict) -> dict:
    if constraints_in is None:
        constraints_in = {}

    must = clamp_minute(constraints_in.get("must_wake_by_min"))
    pref = clamp_minute(constraints_in.get("preferred_wake_min"))

    if pref is None:
        pref = clamp_minute(baseline.get("median_wake_min"))
    if pref is None:
        pref = 480
    if must is None:
        must = pref

    hard = constraints_in.get("hard_constraints", {}) or {}
    soft = constraints_in.get("soft_constraints", {}) or {}

    no_bed_after = clamp_minute(hard.get("no_bed_after_min"))
    min_opp = hard.get("min_sleep_opportunity_min", None)
    try:
        min_opp = int(round(float(min_opp))) if min_opp is not None else None
    except Exception:
        min_opp = None

    avoid_high   = bool(soft.get("avoid_high_intensity_near_bed", False))
    caffeine_cut = clamp_minute(soft.get("caffeine_cutoff_min"))

    soft_norm = dict(soft)
    soft_norm["avoid_high_intensity_near_bed"] = avoid_high
    soft_norm["caffeine_cutoff_min"]            = caffeine_cut

    return {
        "must_wake_by_min":    int(must),
        "preferred_wake_min":  int(pref),
        "hard_constraints": {
            "no_bed_after_min":         no_bed_after,
            "min_sleep_opportunity_min": min_opp,
        },
        "soft_constraints": soft_norm,
    }

# ── Data helpers ───────────────────────────────────────────────────────────────

def recent_nights(df: pd.DataFrame, n=30) -> pd.DataFrame:
    df   = df.sort_values("sleep_date")
    keep = df[df["bedtime"].notna() & df["wake_time"].notna() & df["total_sleep_min"].notna()].copy()
    return keep.tail(n)

def infer_baseline(df_recent: pd.DataFrame) -> dict:
    bt      = to_min_of_day(df_recent["bedtime"])
    wt      = to_min_of_day(df_recent["wake_time"])
    bt_wrap = bt.map(wrap_minutes)
    return {
        "median_sleep_min":     float(df_recent["total_sleep_min"].median()),
        "median_bedtime_wrap":  float(bt_wrap.median()),
        "median_wake_min":      float(wt.median()),
        "wake_std_min":         float(wt.std()) if wt.notna().sum() >= 3 else None,
    }

def estimate_sleep_debt(df_recent: pd.DataFrame, target_min: int) -> float:
    last7    = df_recent.tail(7)
    deficits = (target_min - last7["total_sleep_min"]).clip(lower=0)
    return float(deficits.sum())

# ── Candidate generation ───────────────────────────────────────────────────────

def generate_wake_candidates(constraints: dict):
    must = int(constraints["must_wake_by_min"])
    pref = int(constraints["preferred_wake_min"])
    candidates = []
    for delta in range(-120, 61, 15):
        w = pref + delta
        if 0 <= w <= must:
            candidates.append(w)
    candidates.append(must)
    return sorted(set(candidates))

def generate_bed_candidates(now_min, wake_min, desired_sleep_min):
    ideal_bed      = (wake_min - desired_sleep_min) % 1440
    bed_candidates = []
    # Wider window: -90 to +180 min around ideal to handle late-night sessions
    for delta in range(-90, 181, 15):
        bed_candidates.append((ideal_bed + delta) % 1440)
    # Also always include "right now + 15 min" as a candidate
    bed_candidates.append((now_min + 15) % 1440)
    def minutes_until(bed):
        return (bed - now_min) % 1440
    # Allow up to 14 hours ahead (was 12) to handle edge cases
    filtered = [b for b in bed_candidates if minutes_until(b) <= 14 * 60]
    return sorted(set(filtered))

# ── Scoring ────────────────────────────────────────────────────────────────────

def bedtime_score(bed_wrap, baseline_bed_wrap, mins_until_bed):
    d         = circ_dist(bed_wrap, baseline_bed_wrap)
    closeness = max(0.0, 1.0 - d / 180.0)
    if mins_until_bed < 15:
        realism = 0.0
    elif mins_until_bed < 30:
        realism = 0.25
    elif mins_until_bed < 60:
        realism = 0.6
    else:
        realism = 1.0
    return closeness * realism

def soft_penalties(bed_min: int, constraints: dict, baseline: dict):
    soft    = (constraints.get("soft_constraints") or {})
    hard    = (constraints.get("hard_constraints") or {})
    penalty = 0.0
    details = {}

    baseline_bed_clock = int((baseline["median_bedtime_wrap"] + 720) % 1440)

    if soft.get("avoid_high_intensity_near_bed", False):
        cap_hard = hard.get("no_bed_after_min")
        cap_soft = baseline_bed_clock
        if cap_hard is not None:
            cap_soft = min(int(cap_soft), int(cap_hard))
        window  = int(SOFT_WEIGHTS["late_bed_window_min"])
        dt_late = bed_min - cap_soft
        if 0 < dt_late <= window:
            frac    = dt_late / max(1, window)
            p       = SOFT_WEIGHTS["late_bed_penalty_max"] * frac
            penalty += p
            details["late_bed_penalty"]    = round(p, 3)
            details["late_bed_anchor_min"] = int(cap_soft)
            details["late_bed_window_min"] = int(window)

    cutoff = soft.get("caffeine_cutoff_min", None)
    if cutoff is not None:
        window = int(SOFT_WEIGHTS["caffeine_window_min"])
        dt     = bed_min - int(cutoff)
        if 0 <= dt <= window:
            frac    = 1.0 - (dt / max(1, window))
            p       = SOFT_WEIGHTS["caffeine_penalty_max"] * frac
            penalty += p
            details["caffeine_penalty"]    = round(p, 3)
            details["caffeine_cutoff_min"] = int(cutoff)
            details["caffeine_window_min"] = int(window)

    details["soft_penalty_total"] = round(penalty, 3)
    return penalty, details

def score_plan(now_min, bed_min, wake_min, baseline, constraints, desired_sleep_min):
    must         = int(constraints["must_wake_by_min"])
    target_wake  = int(constraints["preferred_wake_min"])

    if wake_min > must:
        return None

    mins_until_bed = (bed_min - now_min) % 1440
    if mins_until_bed > 12 * 60:
        return None

    no_bed_after = constraints.get("hard_constraints", {}).get("no_bed_after_min")
    if no_bed_after is not None and bed_min > int(no_bed_after):
        return None

    sleep_opp = (wake_min - bed_min) % 1440
    min_opp   = constraints.get("hard_constraints", {}).get("min_sleep_opportunity_min")
    if min_opp is not None and sleep_opp < int(min_opp):
        return None

    sleep_score = min(1.0, sleep_opp / max(1, desired_sleep_min))
    wake_d      = circ_dist(wake_min, target_wake)
    wake_score  = max(0.0, 1.0 - wake_d / 120.0)
    bed_wrap    = wrap_minutes(bed_min)
    bt_score    = bedtime_score(bed_wrap, baseline["median_bedtime_wrap"], mins_until_bed)

    score = 2.2 * sleep_score + 1.0 * wake_score + 1.2 * bt_score

    penalty, soft_dbg = soft_penalties(bed_min, constraints, baseline)
    score -= penalty

    why = {
        "desired_sleep_min":        int(desired_sleep_min),
        "sleep_opp_min":            int(sleep_opp),
        "mins_until_bedtime":       int(mins_until_bed),
        "sleep_score":              round(sleep_score, 2),
        "wake_score":               round(wake_score, 2),
        "bedtime_score":            round(bt_score, 2),
        "target_wake_min":          int(target_wake),
        "no_bed_after_min":         int(no_bed_after) if no_bed_after is not None else None,
        "min_sleep_opportunity_min": int(min_opp) if min_opp is not None else None,
        **soft_dbg,
    }
    return score, why

def desired_sleep_from_debt(target_min, debt_min):
    extra = min(180, max(0, debt_min / 7))
    return int(min(720, target_min + extra))

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    profile        = load_json(SLEEP_PROFILE)
    constraints_in = load_json(CONSTRAINTS)
    nightly        = pd.read_csv(SLEEP_NIGHTLY)

    now     = datetime.now()
    now_min = minutes_from_midnight(now)

    target_min = int(profile.get("target_sleep_min", TARGET_MIN_DEFAULT))

    recent = recent_nights(nightly, n=30)
    if len(recent) < 5:
        recent = recent_nights(nightly, n=10)

    baseline         = infer_baseline(recent)
    debt             = estimate_sleep_debt(recent, target_min)

    # ── Nap adjustment: subtract today's nap from sleep debt ──────────────────
    nap_credit = 0.0
    if NAP_LOG.exists():
        try:
            nap_entry = json.loads(NAP_LOG.read_text())
            if nap_entry.get("date") == date.today().isoformat():
                nap_credit = float(nap_entry.get("duration_minutes", 0))
                debt = max(0.0, debt - nap_credit)
                print(f"Nap credit applied: {nap_credit} min → adjusted debt: {debt:.1f} min")
        except Exception:
            pass
    # ──────────────────────────────────────────────────────────────────────────

    constraints      = normalize_constraints(constraints_in, baseline)
    desired_sleep_min = desired_sleep_from_debt(target_min, debt)

    wake_candidates = generate_wake_candidates(constraints)

    plans = []
    for w in wake_candidates:
        beds = generate_bed_candidates(now_min, w, desired_sleep_min)
        for b in beds:
            plans.append({"bedtime_min": int(b), "wake_min": int(w)})

    scored = []
    for p in plans:
        res = score_plan(now_min, p["bedtime_min"], p["wake_min"], baseline, constraints, desired_sleep_min)
        if res is None:
            continue
        s, dbg = res
        sleep_opp = (p["wake_min"] - p["bedtime_min"]) % 1440
        p["sleep_opportunity_min"] = int(sleep_opp)
        scored.append((s, dbg, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:TOP_K]

    print("\n=== Top sleep plan options ===")
    for i, (s, dbg, p) in enumerate(top, start=1):
        print(f"\n{i}. SCORE {s:.3f}")
        print(f"   Bed: {fmt_time(p['bedtime_min'])}  |  Wake: {fmt_time(p['wake_min'])}")
        print(f"   Sleep opportunity: {p['sleep_opportunity_min']} min")
        print("   Why:", dbg)

    if not top:
        print("\nNo scored plans found — generating fallback plan based on current time.")
        # Fallback: bed = now + 15 min, wake = bed + desired_sleep_min
        fallback_bed  = (now_min + 15) % 1440
        fallback_wake = (fallback_bed + desired_sleep_min) % 1440
        # If there's a must_wake_by hard constraint, respect it
        must = constraints.get("must_wake_by_min")
        if must is not None and fallback_wake > int(must):
            fallback_wake = int(must)
        fallback_opp = (fallback_wake - fallback_bed) % 1440
        best_score = 0.0
        best_dbg   = {
            "fallback": True,
            "reason": "No feasible plans found within constraints — using current-time fallback.",
            "desired_sleep_min": int(desired_sleep_min),
            "sleep_opp_min": int(fallback_opp),
        }
        best_plan = {
            "bedtime_min": int(fallback_bed),
            "wake_min": int(fallback_wake),
            "sleep_opportunity_min": int(fallback_opp),
        }
    else:
        best_score, best_dbg, best_plan = top[0]
    payload = {
        "generated_at":        now.isoformat(),
        "now_min":             int(now_min),
        "bedtime_min":         int(best_plan["bedtime_min"]),
        "wake_min":            int(best_plan["wake_min"]),
        "sleep_opportunity_min": int(best_plan["sleep_opportunity_min"]),
        "desired_sleep_min":   int(desired_sleep_min),
        "debt_min":            float(debt),
        "nap_credit_min":      float(nap_credit),
        "constraints":         constraints,
        "baseline":            baseline,
        "score":               float(best_score),
        "why":                 best_dbg,
    }
    with open(PLAN_OUT, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\nWrote plan → {PLAN_OUT}")


if __name__ == "__main__":
    main()