import json
from datetime import datetime
import pandas as pd

SLEEP_PROFILE = "data/sleep_profile.json"
SLEEP_NIGHTLY = "data/sleep_index_nightly.csv"
CONSTRAINTS   = "data/tomorrow_constraints.json"   # optional

TOP_K = 5
TARGET_MIN_DEFAULT = 480  # 8h

# ----------------- IO helpers -----------------

def load_json(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
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
    # shift by 12 hours so midnight-ish bedtimes cluster together
    return (m - 720) % 1440

def circ_dist(a, b, period=1440):
    d = abs(a - b) % period
    return min(d, period - d)

def to_min_of_day(series_dt) -> pd.Series:
    dt = pd.to_datetime(series_dt, errors="coerce")
    return (dt.dt.hour * 60 + dt.dt.minute).astype("float")

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

def clamp_minute(x):
    if x is None:
        return None
    try:
        x = int(round(float(x)))
    except Exception:
        return None
    return max(0, min(1439, x))

def generate_wake_candidates(constraints_in, baseline):
    # must_wake_by_min = latest allowable wake time
    must = clamp_minute(constraints_in.get("must_wake_by_min"))
    pref = clamp_minute(constraints_in.get("preferred_wake_min"))

    # defaults
    if pref is None:
        pref = clamp_minute(baseline.get("median_wake_min"))
        if pref is None:
            pref = 480  # final fallback: 8:00 AM

    if must is None:
        must = pref  # if no hard constraint, treat preferred as latest allowed

    # candidate wake times around preferred, but never later than must
    candidates = []
    for delta in range(-120, 61, 15):  # 2h earlier ... 1h later
        w = pref + delta
        if 0 <= w <= must:
            candidates.append(w)

    # always include must
    candidates.append(must)

    candidates = sorted(set(candidates))
    normalized_constraints = {
        "must_wake_by_min": must,
        "preferred_wake_min": pref
    }
    return candidates, normalized_constraints

def generate_bed_candidates(now_min, wake_min, desired_sleep_min):
    # ideal bedtime to get desired sleep
    ideal_bed = (wake_min - desired_sleep_min) % 1440

    bed_candidates = []
    for delta in range(-60, 121, 15):  # 1h earlier ... 2h later than ideal
        bed_candidates.append((ideal_bed + delta) % 1440)

    def minutes_until(bed):
        return (bed - now_min) % 1440

    # keep bedtimes in the next 12 hours (so we don't recommend tomorrow night)
    filtered = [b for b in bed_candidates if minutes_until(b) <= 12 * 60]
    return sorted(set(filtered))

# ----------------- scoring -----------------

def bedtime_score(bed_wrap, baseline_bed_wrap, mins_until_bed):
    # closeness to baseline bedtime (0..1)
    d = circ_dist(bed_wrap, baseline_bed_wrap)
    closeness = max(0.0, 1.0 - d / 180.0)  # within ~3 hours gets credit

    # realism penalty: too-soon bedtime is hard to execute
    if mins_until_bed < 15:
        realism = 0.0
    elif mins_until_bed < 30:
        realism = 0.25
    elif mins_until_bed < 60:
        realism = 0.6
    else:
        realism = 1.0

    return closeness * realism

def score_plan(now_min, bed_min, wake_min, baseline, constraints, desired_sleep_min):
    must = int(constraints["must_wake_by_min"])
    pref = constraints.get("preferred_wake_min", None)
    target_wake = int(pref) if pref is not None else int(round(baseline["median_wake_min"]))

    # feasibility
    # wake cannot be later than must
    if wake_min > must:
        return None

    mins_until_bed = (bed_min - now_min) % 1440
    if mins_until_bed > 12 * 60:
        return None

    # sleep opportunity (wrap-safe)
    sleep_opp = (wake_min - bed_min) % 1440

    # sleep_score: cap at desired sleep
    sleep_score = min(1.0, sleep_opp / max(1, desired_sleep_min))

    # wake_score: closeness to target wake within 2h
    wake_d = circ_dist(wake_min, target_wake)
    wake_score = max(0.0, 1.0 - wake_d / 120.0)

    # bedtime_score: compare WRAPPED minutes
    bed_wrap = wrap_minutes(bed_min)
    bt_score = bedtime_score(bed_wrap, baseline["median_bedtime_wrap"], mins_until_bed)

    # combine
    score = 2.2 * sleep_score + 1.0 * wake_score + 1.2 * bt_score

    why = {
        "desired_sleep_min": int(desired_sleep_min),
        "sleep_opp_min": int(sleep_opp),
        "mins_until_bedtime": int(mins_until_bed),
        "sleep_score": round(sleep_score, 2),
        "wake_score": round(wake_score, 2),
        "bedtime_score": round(bt_score, 2),
        "target_wake_min": int(target_wake),
    }
    return score, why

def desired_sleep_from_debt(target_min, debt_min):
    # simple policy: ask for more sleep when debt is high, but cap it
    # (you can tune these numbers)
    extra = min(180, max(0, debt_min / 7))  # up to +3h extra
    return int(min(720, target_min + extra))  # cap at 12h

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
        print("Not enough recent nights with bedtime+wake+sleep. Using what we have.")
        recent = recent_nights(nightly, n=10)

    baseline = infer_baseline(recent)
    debt = estimate_sleep_debt(recent, target_min)

    wake_candidates, constraints = generate_wake_candidates(constraints_in, baseline)
    desired_sleep_min = desired_sleep_from_debt(target_min, debt)

    # build plans
    plans = []
    for w in wake_candidates:
        beds = generate_bed_candidates(now_min, w, desired_sleep_min)
        for b in beds:
            plans.append({"bedtime_min": int(b), "wake_min": int(w)})

    # score plans
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

    print("\n=== Context ===")
    print("Now:", now)
    print("Now min:", now_min)
    print("Constraints:", constraints)

    print("\n=== Baseline from recent history ===")
    print(baseline)
    print("Estimated sleep debt (last 7 valid nights):", round(debt, 1), "min")
    print("Desired sleep for tonight (policy):", desired_sleep_min, "min")

    print("\n=== Top sleep plan options ===")
    for i, (s, dbg, p) in enumerate(top, start=1):
        print(f"\n{i}. SCORE {s:.3f}")
        print(f"   Bed: {fmt_time(p['bedtime_min'])}  |  Wake: {fmt_time(p['wake_min'])}")
        print(f"   Sleep opportunity: {p['sleep_opportunity_min']} min")
        print("   Why:", dbg)

if __name__ == "__main__":
    main()
