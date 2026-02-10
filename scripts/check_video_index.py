import pandas as pd

PATH = "data/video_index.csv"

def main():
    df = pd.read_csv(PATH)

    needed = ["id","source","videoId","title","durationMin","category","intensity","url"]
    missing_cols = [c for c in needed if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing columns in video_index.csv: {missing_cols}")

    # Basic checks
    print("Rows:", len(df))
    print("Unique videoId:", df["videoId"].nunique())
    print("\nCategory counts:\n", df["category"].value_counts().head(20))
    print("\nIntensity summary:\n", df["intensity"].describe())

    # Duplicates
    dups = df.duplicated(subset=["videoId"]).sum()
    print("\nDuplicate videoId rows:", dups)

    # Out of bounds
    bad_dur = df[(df["durationMin"] < 2) | (df["durationMin"] > 60)]
    bad_int = df[(df["intensity"] < 0) | (df["intensity"] > 1)]
    print("Bad duration rows:", len(bad_dur))
    print("Bad intensity rows:", len(bad_int))

if __name__ == "__main__":
    main()
