"""
Offline ingestion script: build wind-down video index using YouTube Data API (not scraping).

Inputs:
- data/youtube_seed_queries.txt (one query per line, supports # comments)

Outputs:
- data/video_index.csv (structured catalog used as our "content index")
"""

import os
import re
import math
from datetime import datetime, timezone

import pandas as pd
from dotenv import load_dotenv
from googleapiclient.discovery import build
import firebase_admin
from firebase_admin import credentials, firestore


# -------------------- Config --------------------
load_dotenv()
YT_API_KEY = os.getenv("YT_API_KEY")

QUERIES_PATH = "data/youtube_queries.txt"
OUT_PATH = "data/video_index.csv"

MAX_RESULTS_PER_QUERY = 25        # 1..50 (search.list)
MIN_DURATION_MIN = 2
MAX_DURATION_MIN = 60

# Optional: set region/language for consistency
REGION_CODE = "US"
RELEVANCE_LANGUAGE = "en"

SERVICE_ACCOUNT_PATH = "secrets/serviceAccountKey.json"
FIRESTORE_COLLECTION = "contentItems"


# -------------------- Helpers --------------------

def read_queries(path: str) -> list[str]:
    """Read seed queries (ignore blank lines and # comments)."""
    queries = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            queries.append(line)
    return queries


def iso8601_to_minutes(duration: str) -> int:
    """
    YouTube duration format example: PT15M51S, PT1H2M, PT45S
    Returns minutes, rounded up.
    """
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration or "")
    if not m:
        return 0
    h = int(m.group(1) or 0)
    mi = int(m.group(2) or 0)
    s = int(m.group(3) or 0)
    total_seconds = h * 3600 + mi * 60 + s
    return max(1, math.ceil(total_seconds / 60)) if total_seconds > 0 else 0


def infer_category(title: str, description: str) -> str:
    """
    Lightweight category inference for your index.
    You can refine later—this is enough for v1.
    """
    t = f"{title} {description}".lower()
    if "asmr" in t:
        return "asmr"
    if any(k in t for k in ["meditation", "breathing", "body scan", "mindfulness"]):
        return "meditation"
    if any(k in t for k in ["white noise", "brown noise", "pink noise", "fan noise", "noise"]):
        return "noise"
    if any(k in t for k in ["rain", "ocean", "waves", "forest", "nature", "thunder", "fireplace"]):
        return "nature"
    if any(k in t for k in ["bedtime story", "sleep story", "story"]):
        return "stories"
    if any(k in t for k in ["sleep music", "lofi", "lo-fi", "piano", "instrumental"]):
        return "music"
    if any(k in t for k in ["bedtime yoga", "gentle yoga", "stretch", "stretches", "lying down yoga"]):
        return "gentle_movement"
    return "other"


def estimate_intensity(title: str, description: str) -> float:
    """
    Heuristic intensity score in [0,1]. Lower = calmer.
    This supports filtering + ranking + explanation.
    """
    text = f"{title} {description}".lower()
    score = 0.30

    # calmer cues
    if any(k in text for k in ["rain", "white noise", "brown noise", "pink noise", "ambient", "sleep", "black screen"]):
        score -= 0.12
    if any(k in text for k in ["meditation", "breathing", "asmr", "relax", "calm"]):
        score -= 0.06

    # stimulating cues (we try to avoid these anyway)
    if any(k in text for k in ["true crime", "news", "debate", "politics"]):
        score += 0.40
    if any(k in text for k in ["comedy", "funny", "prank", "reaction"]):
        score += 0.25

    return round(max(0.0, min(1.0, score)), 2)


# -------------------- YouTube API --------------------

def build_client():
    if not YT_API_KEY:
        raise RuntimeError("Missing YT_API_KEY. Put it in .env or export it.")
    return build("youtube", "v3", developerKey=YT_API_KEY)


def search_video_ids(youtube, query: str) -> list[str]:
    """
    Uses search.list to retrieve candidate IDs.
    Filters out live/upcoming using snippet.liveBroadcastContent.
    """
    resp = youtube.search().list(
        q=query,
        part="snippet",
        type="video",
        maxResults=MAX_RESULTS_PER_QUERY,
        safeSearch="strict",
        regionCode=REGION_CODE,
        relevanceLanguage=RELEVANCE_LANGUAGE,
    ).execute()

    ids = []
    for item in resp.get("items", []):
        snippet = item.get("snippet", {}) or {}
        if snippet.get("liveBroadcastContent") != "none":
            continue
        vid = (item.get("id", {}) or {}).get("videoId")
        if vid:
            ids.append(vid)
    return ids


def fetch_details(youtube, id_to_query: dict[str, str]) -> list[dict]:
    """
    Uses videos.list to fetch duration + snippet for IDs (cheap).
    - batches IDs in groups of 50 (API limit)
    - filters by duration bounds
    - excludes live/upcoming again for safety
    """
    video_ids = list(id_to_query.keys())
    rows = []

    # videos.list supports up to 50 IDs per request
    for i in range(0, len(video_ids), 50):
        group = video_ids[i:i + 50]

        resp = youtube.videos().list(
            part="snippet,contentDetails",
            id=",".join(group),
        ).execute()

        for v in resp.get("items", []):
            vid = v.get("id")
            snippet = v.get("snippet", {}) or {}
            content = v.get("contentDetails", {}) or {}

            # second safety check
            if snippet.get("liveBroadcastContent") != "none":
                continue

            title = snippet.get("title", "") or ""
            desc = snippet.get("description", "") or ""
            channel = snippet.get("channelTitle", "") or ""

            duration_min = iso8601_to_minutes(content.get("duration", ""))
            if duration_min < MIN_DURATION_MIN or duration_min > MAX_DURATION_MIN:
                continue

            rows.append({
                "id": f"youtube_{vid}",
                "source": "youtube",
                "videoId": vid,
                "seedQuery": id_to_query.get(vid, ""),
                "title": title,
                "channelTitle": channel,
                "durationMin": int(duration_min),
                "category": infer_category(title, desc),
                "intensity": estimate_intensity(title, desc),
                "url": f"https://www.youtube.com/watch?v={vid}",
                "ingestedAt": datetime.now(timezone.utc).isoformat(),
            })


    return rows

def main():
    youtube = build_client()

    # 1) Load seed queries
    queries = read_queries(QUERIES_PATH)
    print(f"Loaded {len(queries)} queries from {QUERIES_PATH}")

    # 2) search.list per query -> collect candidate IDs + provenance
    id_to_query = {}
    for q in queries:
        ids = search_video_ids(youtube, q)
        print(f'Query "{q}" -> {len(ids)} non-live IDs')
        for vid in ids:
            if vid not in id_to_query:
                id_to_query[vid] = q  # store the first query that found it

    print(f"Unique IDs after dedupe: {len(id_to_query)}")

    # 3) videos.list -> enrich + filter -> build rows
    rows = fetch_details(youtube, id_to_query)
    print(f"Final indexed rows (after filters): {len(rows)}")

    if not rows:
        print("No videos survived filtering (live/duration).")
        return

    # 4) Upload directly to Firestore
    upload_rows_to_firestore(rows)

    # 5) Optional: still write CSV backup for debugging/repro
    df = pd.DataFrame(rows).drop_duplicates(subset=["videoId"])
    os.makedirs("data", exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    print(f"Wrote CSV backup to {OUT_PATH}")

    # Preview
    preview_cols = ["seedQuery", "title", "durationMin", "category", "intensity", "url"]
    preview_cols = [c for c in preview_cols if c in df.columns]
    print(df[preview_cols].head(10).to_string(index=False))


if __name__ == "__main__":
    main()


# -------------------- Main --------------------

def main():
    youtube = build_client()

    # 1) Load seed queries
    queries = read_queries(QUERIES_PATH)
    print(f"Loaded {len(queries)} queries from {QUERIES_PATH}")

    # 2) search.list per query -> collect candidate IDs
    id_to_query = {}

    for q in queries:
        ids = search_video_ids(youtube, q)
        print(f'Query "{q}" -> {len(ids)} non-live IDs')
        for vid in ids:
            if vid not in id_to_query:
                id_to_query[vid] = q 
    
    print(f"Unique IDs after dedupe: {len(id_to_query)}")
    
    # 4) videos.list -> enrich + filter -> build rows
    rows = fetch_details(youtube, id_to_query)
    df = pd.DataFrame(rows).drop_duplicates(subset=["videoId"])

    # 5) Write index CSV
    os.makedirs("data", exist_ok=True)
    df.to_csv(OUT_PATH, index=False)

    print(f"Wrote {len(df)} videos to {OUT_PATH}")
    if len(df) > 0:
        print(df[["title", "durationMin", "category", "intensity", "url"]].head(10).to_string(index=False))


if __name__ == "__main__":
    main()