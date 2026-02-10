import json
from datetime import datetime
import pandas as pd

SLEEP_PROFILE = "data/sleep_profile.json"
SLEEP_NIGHTLY = "data/sleep_index_nightly.csv"
VIDEO_INDEX   = "data/video_index.csv"

TONIGHT_PLAN = "data/tonight_plan.json"

TOP_N = 10

# tweak these anytime
CATEGORY_WEIGHTS = {
    "noise": 1.15,
    "nature": 1.10,
    "meditation": 1.05,
    "asmr": 1.00,
    "stories": 0.95,
    "music": 0.95,
    "gentle_movement": 0.90,
    "other": 0.85,
}

def load_json(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def load_profile(path):
    with open(path, "r") as f:
        return json.load(f)

def minutes_from_midnight(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute

def wrap_minutes(m: float) -> float:
    # same wrapping idea as before: midnight-safe
    return (m - 720) % 1440

def choose_tonight_context(profile: dict, plan: dict):
    now = datetime.now()
    now_min = minutes_from_midnight(now)

    # use the plan bedtime if present, else profile, else 11:30pm
    target_bedtime_min = plan.get("bedtime_min", profile.get("target_bedtime_min"))
    if target_bedtime_min is None:
        target_bedtime_min = 23 * 60 + 30

    target_bedtime_min = int(target_bedtime_min)

    mins_until = (target_bedtime_min - now_min) % 1440
    if mins_until > 12 * 60:
        mins_until = 0

    return {
        "now": now,
        "now_min": now_min,
        "target_bedtime_min": target_bedtime_min,
        "mins_until_bedtime": int(mins_until),
        "planned_wake_min": plan.get("wake_min"),
    }


def latest_nightly_features(nightly_df: pd.DataFrame) -> dict:
    # use most recent row with non-null values where possible
    nightly_df = nightly_df.sort_values("sleep_date")
    last = nightly_df.iloc[-1].to_dict()

    return {
        "sleep_debt_7n_min": float(last.get("sleep_debt_7n_min")) if pd.notna(last.get("sleep_debt_7n_min")) else 0.0,
        "bedtime_drift_min": float(last.get("bedtime_drift_min")) if pd.notna(last.get("bedtime_drift_min")) else 0.0,
        "bedtime_std_7n": float(last.get("bedtime_std_7n")) if pd.notna(last.get("bedtime_std_7n")) else None,
        "wake_std_7n": float(last.get("wake_std_7n")) if "wake_std_7n" in nightly_df.columns and pd.notna(last.get("wake_std_7n")) else None,
        "most_recent_sleep_date": str(last.get("sleep_date")),
        "most_recent_total_sleep_min": float(last.get("total_sleep_min")) if pd.notna(last.get("total_sleep_min")) else None,
    }

def score_row(row, ctx, feats, profile):
    """
    Higher score = better recommendation.
    """
    duration = float(row["durationMin"])
    intensity = float(row["intensity"])
    category = row.get("category", "other")

    mins_until = ctx["mins_until_bedtime"]
    sleep_debt = feats["sleep_debt_7n_min"]
    drift = feats["bedtime_drift_min"]

    # --- duration fit ---
    # if close to bedtime, prefer short; if lots of time, allow longer
    # cap "recommended duration" by mins_until
    duration_fit = 1.0
    if mins_until <= 10:
        # basically bedtime: only super short stuff
        duration_fit = 1.0 if duration <= 8 else 0.2
    elif mins_until <= 30:
        duration_fit = 1.0 if duration <= mins_until else 0.5
    else:
        # plenty of time: mild preference for <= 30
        duration_fit = 1.0 if duration <= 30 else 0.85

    # --- intensity preference ---
    # if sleep debt is high OR drift is getting later, penalize intensity more
    intensity_penalty_strength = 1.0
    if sleep_debt >= 180:   # 3h+ debt
        intensity_penalty_strength += 0.4
    if drift >= 30:         # drifting later
        intensity_penalty_strength += 0.3
    if mins_until <= 30:
        intensity_penalty_strength += 0.3

    intensity_score = 1.0 - (intensity_penalty_strength * intensity)
    intensity_score = max(0.0, intensity_score)

    # --- category weights ---
    cat_w = CATEGORY_WEIGHTS.get(category, 0.85)

    # --- final score ---
    score = (2.2 * intensity_score) + (1.3 * duration_fit) + (0.6 * cat_w)

    # small bonus if it exactly "fits" the time window
    if duration <= max(5, mins_until):
        score += 0.2

    return score, {
        "mins_until_bedtime": mins_until,
        "duration_fit": round(duration_fit, 2),
        "intensity_score": round(intensity_score, 2),
        "sleep_debt_7n_min": round(sleep_debt, 1),
        "bedtime_drift_min": round(drift, 1),
        "category_weight": round(cat_w, 2),
    }


def recent_nights(nightly_df: pd.DataFrame, n=30) -> pd.DataFrame:
    nightly_df = nightly_df.sort_values("sleep_date")

    # keep only nights that can actually define a schedule
    keep = nightly_df[
        nightly_df["bedtime"].notna()
        & nightly_df["wake_time"].notna()
        & nightly_df["total_sleep_min"].notna()
    ].copy()

    return keep.tail(n)


def explain(row, dbg):
    bits = []
    bits.append(f"{row['category']} · {int(row['durationMin'])} min · intensity {row['intensity']}")
    if dbg["mins_until_bedtime"] <= 30:
        bits.append(f"short pick because {dbg['mins_until_bedtime']} min until target bedtime")
    if dbg["sleep_debt_7n_min"] >= 180:
        bits.append(f"high sleep debt (~{int(dbg['sleep_debt_7n_min'])} min) → lower intensity")
    if dbg["bedtime_drift_min"] >= 30:
        bits.append("bedtime drifting later → avoid stimulating content")
    return " | ".join(bits)

def main():
    profile = load_profile(SLEEP_PROFILE)
    plan = load_json(TONIGHT_PLAN)
    nightly = pd.read_csv(SLEEP_NIGHTLY)
    videos = pd.read_csv(VIDEO_INDEX)

    ctx = choose_tonight_context(profile, plan)
    feats = latest_nightly_features(nightly)

    scored = []
    for _, row in videos.iterrows():
        s, dbg = score_row(row, ctx, feats, profile)
        scored.append((s, dbg, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:TOP_N]

    print("\n=== Context ===")
    print("Now:", ctx["now"])
    print("Minutes until target bedtime:", ctx["mins_until_bedtime"])
    print("\n=== Latest sleep features ===")
    print(feats)

    print("\n=== Top recommendations ===")
    for rank, (s, dbg, row) in enumerate(top, start=1):
        print(f"\n{rank}. SCORE {s:.3f} — {row['title']}")
        print("   ", explain(row, dbg))
        print("    ", row["url"])

if __name__ == "__main__":
    main()
