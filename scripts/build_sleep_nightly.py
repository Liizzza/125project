import pandas as pd

IN_CSV = "data/sleep_records.csv"
OUT_CSV = "data/sleep_index_nightly.csv"

ASLEEP_VALUES = {
    "HKCategoryValueSleepAnalysisAsleepCore",
    "HKCategoryValueSleepAnalysisAsleepDeep",
    "HKCategoryValueSleepAnalysisAsleepREM",
    "HKCategoryValueSleepAnalysisAsleepUnspecified",
    "HKCategoryValueSleepAnalysisAsleep",
}
AWAKE_VALUES = {"HKCategoryValueSleepAnalysisAwake"}
INBED_VALUES = {"HKCategoryValueSleepAnalysisInBed"}


def parse_dt(s: str):
    return pd.to_datetime(s, format="%Y-%m-%d %H:%M:%S %z", errors="coerce")


def night_key(dt):
    return (dt - pd.Timedelta(hours=12)).date()


def wrap_minutes(minutes_series):
    """Wrap-safe minutes: shift by 12h so midnight-ish times cluster together."""
    return (minutes_series - 720) % 1440


def wrap_diff(diff_series):
    """Clamp diffs to [-720, 720] to avoid wrap artifacts."""
    return ((diff_series + 720) % 1440) - 720


def main():
    df = pd.read_csv(IN_CSV)

    df["start"] = df["startDate"].map(parse_dt)
    df["end"] = df["endDate"].map(parse_dt)
    df = df.dropna(subset=["start", "end"]).copy()

    df["minutes"] = (df["end"] - df["start"]).dt.total_seconds() / 60.0
    df = df[df["minutes"] > 0].copy()

    df["sleep_date"] = df["start"].map(night_key)

    df["is_asleep"] = df["value"].isin(ASLEEP_VALUES)
    df["is_awake"] = df["value"].isin(AWAKE_VALUES)
    df["is_inbed"] = df["value"].isin(INBED_VALUES)

    # -------------------------
    # Bedtime / wake time (PER-NIGHT fallback)
    # -------------------------
    inbed_bw = (
        df[df["is_inbed"]]
        .groupby("sleep_date")
        .agg(
            bedtime=("start", "min"),
            wake_time=("end", "max"),
            inbed_minutes=("minutes", "sum"),
        )
    )

    asleep_bw = (
        df[df["is_asleep"]]
        .groupby("sleep_date")
        .agg(
            bedtime_asleep=("start", "min"),
            wake_asleep=("end", "max"),
            asleep_window_minutes=("minutes", "sum"),
        )
    )

    bedwake = inbed_bw.join(asleep_bw, how="outer")
    bedwake["bedtime"] = bedwake["bedtime"].fillna(bedwake["bedtime_asleep"])
    bedwake["wake_time"] = bedwake["wake_time"].fillna(bedwake["wake_asleep"])
    bedwake = bedwake.drop(columns=["bedtime_asleep", "wake_asleep"])

    # -------------------------
    # Totals from stage segments
    # -------------------------
    asleep_totals = (
        df[df["is_asleep"]]
        .groupby("sleep_date")["minutes"]
        .sum()
        .rename("asleep_minutes")
    )
    awake_totals = (
        df[df["is_awake"]]
        .groupby("sleep_date")["minutes"]
        .sum()
        .rename("awake_minutes")
    )

    out = (
        bedwake
        .join(asleep_totals, how="outer")
        .join(awake_totals, how="outer")
        .reset_index()
        .sort_values("sleep_date")
        .reset_index(drop=True)
    )

    # -------------------------
    # Robust total sleep
    # -------------------------
    out["total_sleep_min"] = out["asleep_minutes"]

    if "inbed_minutes" in out.columns:
        est_from_inbed = out["inbed_minutes"] - out["awake_minutes"].fillna(0)
        out["total_sleep_min"] = out["total_sleep_min"].fillna(est_from_inbed)
        out["total_sleep_min"] = out["total_sleep_min"].fillna(out["inbed_minutes"])

    if "asleep_window_minutes" in out.columns:
        out["total_sleep_min"] = out["total_sleep_min"].fillna(out["asleep_window_minutes"])

    out.loc[out["total_sleep_min"] < 0, "total_sleep_min"] = pd.NA

    # -------------------------
    # Onset latency
    # -------------------------
    first_asleep = (
        df[df["is_asleep"]]
        .groupby("sleep_date")["start"]
        .min()
        .rename("first_asleep_start")
        .reset_index()
    )
    out = out.merge(first_asleep, on="sleep_date", how="left")

    out["sleep_onset_latency_min"] = (
        (out["first_asleep_start"] - out["bedtime"]).dt.total_seconds() / 60.0
    )
    out.loc[out["sleep_onset_latency_min"] < 0, "sleep_onset_latency_min"] = pd.NA

    # efficiency (only when inbed exists)
    if "inbed_minutes" in out.columns:
        out["sleep_efficiency"] = out["asleep_minutes"] / out["inbed_minutes"]
        out.loc[
            (out["sleep_efficiency"] > 1) | (out["sleep_efficiency"] < 0),
            "sleep_efficiency",
        ] = pd.NA
    else:
        out["sleep_efficiency"] = pd.NA

    out["weekday"] = pd.to_datetime(out["sleep_date"]).dt.weekday

    # -------------------------
    # Derived features
    # -------------------------
    TARGET_MIN = 480  # default 8h

    # debt across last 7 recorded nights
    out["sleep_debt_7n_min"] = pd.NA
    valid_sleep = out["total_sleep_min"].notna()
    debt_series = (TARGET_MIN - out.loc[valid_sleep, "total_sleep_min"]).clip(lower=0)
    out.loc[valid_sleep, "sleep_debt_7n_min"] = debt_series.rolling(7, min_periods=3).sum()

    # bedtime minutes, wrap-safe
    bt = pd.to_datetime(out["bedtime"], errors="coerce")
    bedtime_raw = bt.dt.hour * 60 + bt.dt.minute
    out["bedtime_min_wrapped"] = wrap_minutes(bedtime_raw)

    out["bedtime_std_7n"] = out["bedtime_min_wrapped"].rolling(7, min_periods=3).std()

    drift = (
        out["bedtime_min_wrapped"].rolling(3, min_periods=2).mean()
        - out["bedtime_min_wrapped"].shift(3).rolling(3, min_periods=2).mean()
    )
    out["bedtime_drift_min"] = wrap_diff(drift)

    # OPTIONAL: wake consistency (often useful for schedule constraints)
    wt = pd.to_datetime(out["wake_time"], errors="coerce")
    wake_raw = wt.dt.hour * 60 + wt.dt.minute
    out["wake_min_wrapped"] = wrap_minutes(wake_raw)
    out["wake_std_7n"] = out["wake_min_wrapped"].rolling(7, min_periods=3).std()

    out.to_csv(OUT_CSV, index=False)
    print(f"Wrote {OUT_CSV} with {len(out)} nights")


if __name__ == "__main__":
    main()
