import pandas as pd

IN_CSV = "sleep_records.csv"
OUT_CSV = "sleep_index_nightly.csv"

ASLEEP_VALUES = {
    "HKCategoryValueSleepAnalysisAsleepCore",
    "HKCategoryValueSleepAnalysisAsleepDeep",
    "HKCategoryValueSleepAnalysisAsleepREM",
    "HKCategoryValueSleepAnalysisAsleepUnspecified",
}
AWAKE_VALUE = "HKCategoryValueSleepAnalysisAwake"
INBED_VALUE = "HKCategoryValueSleepAnalysisInBed"

def parse_dt(s):
    # Apple export looks like: "2021-09-22 00:07:30 -0800"
    return pd.to_datetime(s, format="%Y-%m-%d %H:%M:%S %z", errors="coerce")

def night_key(dt):
    # Assign segments to the "night of" date:
    # subtract 12 hours so 12:30am counts toward previous evening.
    return (dt - pd.Timedelta(hours=12)).date()

def main():
    df = pd.read_csv(IN_CSV)

    df["start"] = df["startDate"].apply(parse_dt)
    df["end"] = df["endDate"].apply(parse_dt)
    df = df.dropna(subset=["start", "end"])

    df["minutes"] = (df["end"] - df["start"]).dt.total_seconds() / 60.0
    df = df[df["minutes"] > 0]

    df["sleep_date"] = df["start"].apply(night_key)

    df["is_asleep"] = df["value"].isin(ASLEEP_VALUES)
    df["is_awake"] = df["value"].eq(AWAKE_VALUE)
    df["is_inbed"] = df["value"].eq(INBED_VALUE)

    # bed/wake based on InBed segments
    inbed = df[df["is_inbed"]].groupby("sleep_date").agg(
        bedtime=("start", "min"),
        wake_time=("end", "max"),
        inbed_minutes=("minutes", "sum"),
    )

    # asleep/awake totals (from stage segments)
    totals = df.groupby("sleep_date").agg(
        asleep_minutes=("minutes", lambda s: s[df.loc[s.index, "is_asleep"]].sum()),
        awake_minutes=("minutes", lambda s: s[df.loc[s.index, "is_awake"]].sum()),
    )

    out = inbed.join(totals, how="outer").reset_index()

    # first asleep start (for sleep onset latency)
    first_asleep = df[df["is_asleep"]].groupby("sleep_date")["start"].min().rename("first_asleep_start")
    out = out.merge(first_asleep.reset_index(), on="sleep_date", how="left")

    out["sleep_efficiency"] = out["asleep_minutes"] / out["inbed_minutes"]
    out["sleep_onset_latency_min"] = (out["first_asleep_start"] - out["bedtime"]).dt.total_seconds() / 60.0

    # Clean up weird cases
    out.loc[out["sleep_efficiency"].gt(1) | out["sleep_efficiency"].lt(0), "sleep_efficiency"] = pd.NA

    out.to_csv(OUT_CSV, index=False)
    print(f"Wrote {OUT_CSV} with {len(out)} nights")

if __name__ == "__main__":
    main()
