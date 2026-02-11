import json
from datetime import datetime
import pandas as pd

# --------- Pick which user by editing these 4 paths ----------
SLEEP_PROFILE = "data/sleep_profile2.json"
SLEEP_NIGHTLY = "data/sleep_index_nightly2.csv"
CONSTRAINTS   = "data/tomorrow_constraints2.json"   # optional
PLAN_OUT      = "data/tonight_plan2.json"
# ------------------------------------------------------------

TOP_K = 5
TARGET_MIN_DEFAULT = 480  # 8h

# ----------------- soft-constraint tuning -----------------
SOFT_WEIGHTS = {
    "late_bed_penalty_max": 0.35,     # max score penalty for being "too close" to a bedtime cap
    "late_bed_window_min": 60,        # minutes before cap that triggers late-bed penalty
    "caffeine_penalty_max": 0.20,     # max penalty if bedtime is too soon after caffeine cutoff
    "caffeine_window_min": 420,       # 4 hours after cutoff is the "risk window"
}
# -----------------------------------------------------------

# ----------------- IO helpers -----------------

def load_json(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}

def minutes_from_midnight(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute

def fmt_time(mins: int) -> str:
    mins = int(mins) % 1440
    h = mins // 60
    m = mins % 60
    ampm = "AM" if h < 12 else "PM"
    h12 = h % 12
    if h12 == 0:
        h12 = 12
    return f"{h12}:{m:02d} {ampm}"

# ----------------- time math -----------------

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

# ----------------- constraints parsing -----------------

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

    # normalize known soft keys
    avoid_high = bool(soft.get("avoid_high_intensity_near_bed", False))
    caffeine_cutoff = clamp_minute(soft.get("caffeine_cutoff_min"))

    soft_norm = dict(soft)
    soft_norm["avoid_high_intensity_near_bed"] = avoid_high
    soft_norm["caffeine_cutoff_min"] = caffeine_cutoff

    return {
        "must_wake_by_min": int(must),
        "preferred_wake_min": int(pref),
        "hard_constraints": {
            "no_bed_after_min": no_bed_after,
            "min_sleep_opportunity_min": min_opp,
        },
        "soft_constraints": soft_norm,
    }

# ----------------- data selection -----------------

def recent_nights(df: pd.DataFrame, n=30) -> pd.DataFrame:
    df = df.sort_values("sleep_date")
    keep = df[df["bedtime"].notna() & df["wake_time"].notna() & df["total_sleep_min"].notna()].copy()
    return keep.tail(n)

# ----------------- baselines -----------------

def infer_baseline(df_recent: pd.DataFrame) -> dict:
    bt = to_min_of_day(df_recent["bedtime"])
    wt = to_min_of_day(df_recent["wake_time"])
    bt_wrap = bt.map(wrap_minutes)

    return {
        "median_sleep_min": float(df_recent["total_sleep_min"].median()),
        "median_bedtime_wrap": float(bt_wrap.median()),
        "median_wake_min": float(wt.median()),
        "wake_std_min": float(wt.std()) if wt.notna().sum() >= 3 else None,
    }

def estimate_sleep_debt(df_recent: pd.DataFrame, target_min: int) -> float:
    last7 = df_recent.tail(7)
    deficits = (target_min - last7["total_sleep_min"]).clip(lower=0)
    return float(deficits.sum())

# ----------------- candidate generation -----------------

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
    ideal_bed = (wake_min - desired_sleep_min) % 1440

    bed_candidates = []
    for delta in range(-60, 121, 15):
        bed_candidates.append((ideal_bed + delta) % 1440)

    def minutes_until(bed):
        return (bed - now_min) % 1440

    filtered = [b for b in bed_candidates if minutes_until(b) <= 12 * 60]
    return sorted(set(filtered))

# ----------------- scoring -----------------

def bedtime_score(bed_wrap, baseline_bed_wrap, mins_until_bed):
    d = circ_dist(bed_wrap, baseline_bed_wrap)
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
    """
    Returns (penalty_total, details_dict)
    penalty_total is subtracted from the plan score.
    """
    soft = (constraints.get("soft_constraints") or {})
    hard = (constraints.get("hard_constraints") or {})

    penalty = 0.0
    details = {}

    # Helper: interpret baseline wrapped bedtime back onto clock minutes
    baseline_bed_clock = int((baseline["median_bedtime_wrap"] + 720) % 1440)

    # ---- Soft: avoid_high_intensity_near_bed ----
    # Re-interpret as: "avoid late bedtimes vs your typical bedtime"
    if soft.get("avoid_high_intensity_near_bed", False):
        # Soft anchor = baseline bedtime; if you have a hard cap, don't anchor later than it
        cap_hard = hard.get("no_bed_after_min")
        cap_soft = baseline_bed_clock

        if cap_hard is not None:
            cap_soft = min(int(cap_soft), int(cap_hard))

        window = int(SOFT_WEIGHTS["late_bed_window_min"])

        # Penalize being LATER than the soft anchor, up to window minutes
        # Example: anchor 10:00pm, window 120 → 10:30pm gets some penalty
        dt_late = (bed_min - cap_soft)

        if 0 < dt_late <= window:
            frac = dt_late / max(1, window)   # later => bigger penalty
            p = SOFT_WEIGHTS["late_bed_penalty_max"] * frac
            penalty += p
            details["late_bed_penalty"] = round(p, 3)
            details["late_bed_anchor_min"] = int(cap_soft)
            details["late_bed_window_min"] = int(window)

    # ---- Soft: caffeine_cutoff_min ----
    # Interpret as: "if bedtime is within X hours after cutoff, penalize"
    cutoff = soft.get("caffeine_cutoff_min", None)
    if cutoff is not None:
        window = int(SOFT_WEIGHTS["caffeine_window_min"])
        dt = bed_min - int(cutoff)

        if 0 <= dt <= window:
            frac = 1.0 - (dt / max(1, window))  # closer to cutoff => bigger penalty
            p = SOFT_WEIGHTS["caffeine_penalty_max"] * frac
            penalty += p
            details["caffeine_penalty"] = round(p, 3)
            details["caffeine_cutoff_min"] = int(cutoff)
            details["caffeine_window_min"] = int(window)

    details["soft_penalty_total"] = round(penalty, 3)
    return penalty, details


def score_plan(now_min, bed_min, wake_min, baseline, constraints, desired_sleep_min):
    must = int(constraints["must_wake_by_min"])
    target_wake = int(constraints["preferred_wake_min"])

    # ---------- HARD constraints (filtering) ----------
    if wake_min > must:
        return None

    mins_until_bed = (bed_min - now_min) % 1440
    if mins_until_bed > 12 * 60:
        return None

    no_bed_after = constraints.get("hard_constraints", {}).get("no_bed_after_min")
    if no_bed_after is not None and bed_min > int(no_bed_after):
        return None

    sleep_opp = (wake_min - bed_min) % 1440

    min_opp = constraints.get("hard_constraints", {}).get("min_sleep_opportunity_min")
    if min_opp is not None and sleep_opp < int(min_opp):
        return None

    # ---------- Base score components ----------
    sleep_score = min(1.0, sleep_opp / max(1, desired_sleep_min))

    wake_d = circ_dist(wake_min, target_wake)
    wake_score = max(0.0, 1.0 - wake_d / 120.0)

    bed_wrap = wrap_minutes(bed_min)
    bt_score = bedtime_score(bed_wrap, baseline["median_bedtime_wrap"], mins_until_bed)

    score = 2.2 * sleep_score + 1.0 * wake_score + 1.2 * bt_score

    # ---------- SOFT constraints (penalties) ----------
    penalty, soft_dbg = soft_penalties(bed_min, constraints, baseline)
    score = score - penalty

    why = {
        "desired_sleep_min": int(desired_sleep_min),
        "sleep_opp_min": int(sleep_opp),
        "mins_until_bedtime": int(mins_until_bed),
        "sleep_score": round(sleep_score, 2),
        "wake_score": round(wake_score, 2),
        "bedtime_score": round(bt_score, 2),
        "target_wake_min": int(target_wake),
        "no_bed_after_min": int(no_bed_after) if no_bed_after is not None else None,
        "min_sleep_opportunity_min": int(min_opp) if min_opp is not None else None,
        **soft_dbg,  # includes soft_penalty_total + any triggered penalties
    }
    return score, why

def desired_sleep_from_debt(target_min, debt_min):
    extra = min(180, max(0, debt_min / 7))
    return int(min(720, target_min + extra))

# ----------------- main -----------------

def main():
    profile = load_json(SLEEP_PROFILE)
    constraints_in = load_json(CONSTRAINTS)
    nightly = pd.read_csv(SLEEP_NIGHTLY)

    now = datetime.now()
    now_min = minutes_from_midnight(now)

    target_min = int(profile.get("target_sleep_min", TARGET_MIN_DEFAULT))

    recent = recent_nights(nightly, n=30)
    if len(recent) < 5:
        recent = recent_nights(nightly, n=10)

    baseline = infer_baseline(recent)
    debt = estimate_sleep_debt(recent, target_min)

    constraints = normalize_constraints(constraints_in, baseline)
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
        print("\nNo feasible plans found. Loosen constraints (min opp / no bed after) or widen candidate windows.")
        return

    best_score, best_dbg, best_plan = top[0]
    payload = {
        "generated_at": now.isoformat(),
        "now_min": int(now_min),
        "bedtime_min": int(best_plan["bedtime_min"]),
        "wake_min": int(best_plan["wake_min"]),
        "sleep_opportunity_min": int(best_plan["sleep_opportunity_min"]),
        "desired_sleep_min": int(desired_sleep_min),
        "debt_min": float(debt),
        "constraints": constraints,
        "baseline": baseline,
        "score": float(best_score),
        "why": best_dbg,
    }
    with open(PLAN_OUT, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\nWrote plan → {PLAN_OUT}")

if __name__ == "__main__":
    main()
