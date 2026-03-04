import json
import pandas as pd
import os
from pathlib import Path

# Multi-user: API injects USER_DATA_DIR per user. Falls back to "data/" for manual runs.
DATA_DIR = Path(os.environ.get("USER_DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

IN_CSV   = str(DATA_DIR / "sleep_index_nightly.csv")
OUT_JSON = str(DATA_DIR / "sleep_profile.json")


def mean_or_none(s):
    s = pd.to_numeric(s, errors="coerce").dropna()
    return float(s.mean()) if len(s) else None


def main():
    df     = pd.read_csv(IN_CSV).sort_values("sleep_date")
    recent = df.tail(30).copy()

    # Preserve any existing profile fields (e.g. target_sleep_min set by preferences)
    existing = {}
    profile_path = Path(OUT_JSON)
    if profile_path.exists():
        try:
            with open(profile_path) as f:
                existing = json.load(f)
        except Exception:
            pass

    profile = {
        **existing,   # keep user_id, target_sleep_min, preferred_categories etc.
        "n_nights": int(len(recent)),
        "avg_total_sleep_min":      mean_or_none(recent["total_sleep_min"]),
        "recent_sleep_debt_7n_min": mean_or_none(recent["sleep_debt_7n_min"].tail(7)),
        "avg_onset_latency_min":    mean_or_none(recent["sleep_onset_latency_min"]),
        "bedtime_std_7n_min":       mean_or_none(recent["bedtime_std_7n"].tail(7)),
        "bedtime_drift_min":        mean_or_none(recent["bedtime_drift_min"].tail(7)),
        "last_night": (
            recent.iloc[-1][["sleep_date", "bedtime", "wake_time", "total_sleep_min"]]
            .to_dict()
        ),
    }

    with open(OUT_JSON, "w") as f:
        json.dump(profile, f, indent=2)

    print(f"Wrote {OUT_JSON}")
    print(json.dumps(profile, indent=2))


if __name__ == "__main__":
    main()