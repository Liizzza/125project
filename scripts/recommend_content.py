import json
from datetime import datetime
import pandas as pd
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("USER_DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

SLEEP_PROFILE = str(DATA_DIR / "sleep_profile.json")
SLEEP_NIGHTLY = str(DATA_DIR / "sleep_index_nightly.csv")
TONIGHT_PLAN  = str(DATA_DIR / "tonight_plan.json")
CONTENT_OUT   = str(DATA_DIR / "tonight_content.json")

_SCRIPT_DIR = Path(__file__).parent
VIDEO_INDEX = str(_SCRIPT_DIR.parent / "data" / "video_index.csv")

TOP_N = 50
MAX_PER_CATEGORY = 2

CATEGORY_WEIGHTS = {
    "noise":           1.15,
    "nature":          1.10,
    "meditation":      1.05,
    "asmr":            1.00,
    "stories":         0.95,
    "music":           0.95,
    "gentle_movement": 0.90,
    "other":           0.85,
}

def load_json(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def load_profile(path):
    with open(path, "r") as f:
        return json.load(f)

def minutes_from_midnight(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute

def choose_tonight_context(profile: dict, plan: dict):
    now     = datetime.now()
    now_min = minutes_from_midnight(now)
    target_bedtime_min = plan.get("bedtime_min", profile.get("target_bedtime_min"))
    if target_bedtime_min is None:
        target_bedtime_min = 23 * 60 + 30
    target_bedtime_min = int(target_bedtime_min)

    mins_until = (target_bedtime_min - now_min) % 1440
    # If more than 12 hours away, treat as 0 (bedtime has passed or just started)
    if mins_until > 12 * 60:
        mins_until = 0

    return {
        "now_iso":            now.isoformat(),
        "now_min":            now_min,
        "target_bedtime_min": target_bedtime_min,
        "mins_until_bedtime": int(mins_until),
        "planned_wake_min":   plan.get("wake_min"),
    }

def latest_nightly_features(nightly_df: pd.DataFrame) -> dict:
    nightly_df = nightly_df.sort_values("sleep_date")
    last       = nightly_df.iloc[-1].to_dict()
    return {
        "sleep_debt_7n_min":           float(last.get("sleep_debt_7n_min"))  if pd.notna(last.get("sleep_debt_7n_min"))  else 0.0,
        "bedtime_drift_min":           float(last.get("bedtime_drift_min"))  if pd.notna(last.get("bedtime_drift_min"))  else 0.0,
        "bedtime_std_7n":              float(last.get("bedtime_std_7n"))     if pd.notna(last.get("bedtime_std_7n"))     else None,
        "wake_std_7n":                 float(last.get("wake_std_7n"))        if "wake_std_7n" in nightly_df.columns and pd.notna(last.get("wake_std_7n")) else None,
        "most_recent_sleep_date":      str(last.get("sleep_date")),
        "most_recent_total_sleep_min": float(last.get("total_sleep_min"))    if pd.notna(last.get("total_sleep_min"))    else None,
    }

def score_row(row, ctx, feats, profile, force_stage_b=False):
    duration  = float(row["durationMin"])
    intensity = float(row["intensity"])
    category  = row.get("category", "other")

    mins_until = ctx["mins_until_bedtime"]
    sleep_debt = feats["sleep_debt_7n_min"]
    drift      = feats["bedtime_drift_min"]

    # If past bedtime or very close, treat as stage B
    effective_mins = mins_until if mins_until > 0 else 0
    in_stage_b = force_stage_b or effective_mins <= 45

    # Duration fit
    if effective_mins <= 10 or in_stage_b:
        duration_fit = 1.0 if duration <= 12 else 0.3
    elif effective_mins <= 30:
        duration_fit = 1.0 if duration <= effective_mins else 0.5
    else:
        duration_fit = 1.0 if duration <= 30 else 0.85

    # Intensity — stricter for stage B
    intensity_penalty_strength = 1.0
    if sleep_debt >= 180:
        intensity_penalty_strength += 0.4
    if drift >= 30:
        intensity_penalty_strength += 0.3
    if in_stage_b:
        intensity_penalty_strength += 0.5  # extra strict near bed

    ideal = 10 if in_stage_b else 25

    intensity_score = max(0.0, 1.0 - (intensity_penalty_strength * intensity))
    effective_weights = {**CATEGORY_WEIGHTS, **(profile.get("category_weights") or {})}
    cat_w = effective_weights.get(category, 0.85)

    if in_stage_b:
        stage_cats = profile.get("stage_b_categories") or profile.get("preferred_categories") or []
    else:
        stage_cats = profile.get("stage_a_categories") or profile.get("preferred_categories") or []

    cat_bonus = 0.20 if stage_cats and category in stage_cats else 0.0

    score = (2.2 * intensity_score) + (1.3 * duration_fit) + (0.6 * cat_w) + cat_bonus

    duration_match = max(0.0, 1.0 - min(1.0, abs(duration - ideal) / max(ideal, 1)))
    score += 0.25 * duration_match
    if duration <= max(5, effective_mins if effective_mins > 0 else 12):
        score += 0.2

    return score, {
        "mins_until_bedtime": mins_until,
        "duration_fit":       round(duration_fit, 2),
        "intensity_score":    round(intensity_score, 2),
        "sleep_debt_7n_min":  round(sleep_debt, 1),
        "bedtime_drift_min":  round(drift, 1),
        "category_weight":    round(cat_w, 2),
        "category_bonus":     round(cat_bonus, 2),
        "stage":              "B" if in_stage_b else "A",
    }

def diversify(scored_list, max_per_cat=MAX_PER_CATEGORY):
    counts = {}
    result = []
    for item in scored_list:
        cat = str(item[2].get("category", "other"))
        if counts.get(cat, 0) < max_per_cat:
            result.append(item)
            counts[cat] = counts.get(cat, 0) + 1
    return result

def explain(row, dbg):
    bits = [f"{row['category']} · {int(row['durationMin'])} min · intensity {row['intensity']}"]
    mins = dbg["mins_until_bedtime"]
    if mins <= 30:
        bits.append(f"short pick because {mins} min until target bedtime" if mins > 0 else "short pick because it's bedtime")
    if dbg["sleep_debt_7n_min"] >= 180:
        bits.append(f"high sleep debt (~{int(dbg['sleep_debt_7n_min'])} min) → lower intensity")
    if dbg["bedtime_drift_min"] >= 30:
        bits.append("bedtime drifting later → avoid stimulating content")
    if dbg.get("category_bonus", 0) > 0:
        bits.append(f"matches your Stage {dbg.get('stage', 'A')} category preference")
    return " | ".join(bits)

def main():
    profile = load_profile(SLEEP_PROFILE)
    plan    = load_json(TONIGHT_PLAN)
    if not plan:
        raise FileNotFoundError(f"Missing or empty plan file: {TONIGHT_PLAN}.")

    nightly = pd.read_csv(SLEEP_NIGHTLY)
    videos  = pd.read_csv(VIDEO_INDEX)

    ctx   = choose_tonight_context(profile, plan)
    feats = latest_nightly_features(nightly)

    mins_until = ctx["mins_until_bedtime"]

    # Score all videos for stage A context
    all_scored_a = []
    for _, row in videos.iterrows():
        s, dbg = score_row(row, ctx, feats, profile, force_stage_b=False)
        all_scored_a.append((s, dbg, row))
    all_scored_a.sort(key=lambda x: x[0], reverse=True)

    # Score all videos for stage B context (always force stage B logic)
    all_scored_b = []
    for _, row in videos.iterrows():
        s, dbg = score_row(row, ctx, feats, profile, force_stage_b=True)
        all_scored_b.append((s, dbg, row))
    all_scored_b.sort(key=lambda x: x[0], reverse=True)

    # Stage A: top diverse picks scored as stage A
    # If past bedtime (mins_until == 0), stage A gets fewer slots
    stage_a_count = 10 if mins_until > 45 else 5
    stage_a = diversify(all_scored_a)[:stage_a_count]

    # Stage B: always scored with stage B logic, always has content
    # Filter to short/gentle, fallback to top low-intensity if none qualify
    stage_b_candidates = [
        item for item in all_scored_b
        if float(item[2]["durationMin"]) <= 12 and float(item[2]["intensity"]) <= 0.20
    ]
    if len(stage_b_candidates) < 3:
        # Fallback: just take lowest intensity videos
        stage_b_candidates = sorted(all_scored_b, key=lambda x: float(x[2]["intensity"]))

    stage_b = diversify(stage_b_candidates)[:8]

    def fmt_recs(items):
        return [
            {
                "rank":        i + 1,
                "score":       float(s),
                "title":       str(row["title"]),
                "url":         str(row["url"]),
                "category":    str(row.get("category", "other")),
                "durationMin": float(row["durationMin"]),
                "intensity":   float(row["intensity"]),
                "why":         dbg,
                "explain":     explain(row, dbg),
            }
            for i, (s, dbg, row) in enumerate(items)
        ]

    out = {
        "generated_at": datetime.now().isoformat(),
        "context":      ctx,
        "latest_sleep_features": feats,
        "top_n": TOP_N,
        # Keep flat recommendations for backwards compat
        "recommendations": fmt_recs(diversify(all_scored_a)[:TOP_N]),
        # Stage-split for the bundle
        "stage_a_recommendations": fmt_recs(stage_a),
        "stage_b_recommendations": fmt_recs(stage_b),
    }

    with open(CONTENT_OUT, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote content → {CONTENT_OUT}")
    print(f"Stage A: {len(stage_a)} videos | Stage B: {len(stage_b)} videos")
    print(f"mins_until_bedtime: {mins_until}")

if __name__ == "__main__":
    main()