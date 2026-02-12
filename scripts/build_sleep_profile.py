import json
import pandas as pd

IN_CSV = "data/sleep_index_nightly2.csv"
OUT_JSON = "data/sleep_profile2.json"

def mean_or_none(s):
    s = pd.to_numeric(s, errors="coerce").dropna()
    return float(s.mean()) if len(s) else None

def main():
    df = pd.read_csv(IN_CSV).sort_values("sleep_date")
    recent = df.tail(30).copy()  # last 30 recorded nights

    profile = {
        "n_nights": int(len(recent)),
        "avg_total_sleep_min": mean_or_none(recent["total_sleep_min"]),
        "recent_sleep_debt_7n_min": mean_or_none(recent["sleep_debt_7n_min"].tail(7)),
        "avg_onset_latency_min": mean_or_none(recent["sleep_onset_latency_min"]),
        "bedtime_std_7n_min": mean_or_none(recent["bedtime_std_7n"].tail(7)),
        "bedtime_drift_min": mean_or_none(recent["bedtime_drift_min"].tail(7)),
        "last_night": recent.iloc[-1][["sleep_date","bedtime","wake_time","total_sleep_min"]].to_dict(),
    }

    with open(OUT_JSON, "w") as f:
        json.dump(profile, f, indent=2)
    print(f"Wrote {OUT_JSON}")
    print(json.dumps(profile, indent=2))

if __name__ == "__main__":
    main()
