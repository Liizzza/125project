import pandas as pd
from datetime import datetime

VIDEO_INDEX = "data/video_index.csv"

# --- configurable knobs ---
STAGE_A_MAX_BEFORE_BED_MIN = 45
STAGE_A_DUR_RANGE = (28, 50)     # minutes
STAGE_B_DUR_RANGE = (8, 16)      # minutes
NOISE_DUR_RANGE   = (25, 70)     # minutes

# preference order when sleep debt is high / drifting later
STAGE_A_PREF_CATS = ["nature", "music", "meditation", "gentle_movement", "stories"]
STAGE_B_PREF_CATS = ["meditation", "gentle_movement"]

# keyword nudges (optional but helps)
STAGE_A_PREF_KW = ["yoga nidra", "body scan", "sleep story", "rain", "singing bowls", "thunderstorm"]
STAGE_B_PREF_KW = ["talk-down", "guided", "fall asleep", "before you sleep", "10 minute"]

def minutes_from_midnight(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute

def pick_best(df, cat_order, dur_range, max_intensity, prefer_kw=None):
    d = df.copy()

    # basic filters
    d = d[d["durationMin"].between(dur_range[0], dur_range[1], inclusive="both")]
    d = d[d["intensity"] <= max_intensity]

    if len(d) == 0:
        return None

    # category rank (lower is better)
    cat_rank = {c:i for i,c in enumerate(cat_order)}
    d["cat_rank"] = d["category"].map(lambda x: cat_rank.get(x, 999))

    # keyword bonus (lower is better)
    if prefer_kw:
        title_lower = d["title"].str.lower().fillna("")
        d["kw_bonus"] = 0
        for kw in prefer_kw:
            d["kw_bonus"] += title_lower.str.contains(kw).astype(int)
        d["kw_rank"] = -d["kw_bonus"]  # more matches => better
    else:
        d["kw_rank"] = 0

    # final sort: category priority, then keywords, then lowest intensity, then duration closest to middle
    mid = (dur_range[0] + dur_range[1]) / 2
    d["dur_dist"] = (d["durationMin"] - mid).abs()

    d = d.sort_values(["cat_rank", "kw_rank", "intensity", "dur_dist"], ascending=[True, True, True, True])
    return d.iloc[0]

def build_sleep_playlist(minutes_until_bed: int):
    df = pd.read_csv(VIDEO_INDEX)

    # normalize types
    df["durationMin"] = pd.to_numeric(df["durationMin"], errors="coerce")
    df["intensity"] = pd.to_numeric(df["intensity"], errors="coerce")
    df = df.dropna(subset=["durationMin", "intensity", "category", "title", "url"])

    # --- decide what "stage A" even means based on time left ---
    # If you're <= 45 min from bed, skip Stage A and go straight to Stage B.
    stage_a_allowed = minutes_until_bed > STAGE_A_MAX_BEFORE_BED_MIN

    picks = {}

    if stage_a_allowed:
        stage_a = pick_best(
            df=df[df["category"].isin(STAGE_A_PREF_CATS)],
            cat_order=STAGE_A_PREF_CATS,
            dur_range=STAGE_A_DUR_RANGE,
            max_intensity=0.18,               # allow a tiny bit more earlier
            prefer_kw=STAGE_A_PREF_KW
        )
        picks["stage_a"] = stage_a

    stage_b = pick_best(
        df=df[df["category"].isin(STAGE_B_PREF_CATS)],
        cat_order=STAGE_B_PREF_CATS,
        dur_range=STAGE_B_DUR_RANGE,
        max_intensity=0.12,                   # keep final stage very calm
        prefer_kw=STAGE_B_PREF_KW
    )
    picks["stage_b"] = stage_b

    noise = pick_best(
        df=df[df["category"].eq("noise")],
        cat_order=["noise"],
        dur_range=NOISE_DUR_RANGE,
        max_intensity=0.20,
        prefer_kw=["pink noise", "brown noise", "white noise", "fan"]
    )
    picks["noise"] = noise

    return picks

def pretty_print(picks):
    def show(label, row):
        if row is None:
            print(f"{label}: (no match)")
            return
        print(f"{label}: {row['title']} | {row['category']} | {int(row['durationMin'])} min | intensity {row['intensity']}")
        print(f"      {row['url']}")

    show("Stage A", picks.get("stage_a"))
    show("Stage B", picks.get("stage_b"))
    show("Noise",   picks.get("noise"))

if __name__ == "__main__":
    # Example: 5 hours until bed = 300 minutes
    picks = build_sleep_playlist(minutes_until_bed=300)
    pretty_print(picks)
