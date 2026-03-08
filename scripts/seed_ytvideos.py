"""
Offline ingestion script: build wind-down video index using YouTube Data API (not scraping).

Inputs:
- data/youtube_queries.txt  (original queries)
- data/youtube_queries2.txt (new queries)

Outputs:
- Firestore collection: contentItems (primary)
- data/video_index.csv (backup)
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

QUERIES_PATHS = [
    "data/youtube_queries.txt",
    "data/youtube_queries2.txt",
]
OUT_PATH = "data/video_index.csv"

MAX_RESULTS_PER_QUERY = 25        # 1..50 (search.list)
MIN_DURATION_MIN = 2
MAX_DURATION_MIN = 480            # raised from 60 to support scenic/slow TV long-form content

# Optional: set region/language for consistency
REGION_CODE = "US"
RELEVANCE_LANGUAGE = "en"

SERVICE_ACCOUNT_PATH = "secrets/serviceAccountKey.json"
FIRESTORE_COLLECTION = "contentItems"


# -------------------- Helpers --------------------

def read_queries(path: str) -> list[str]:
    """Read seed queries (ignore blank lines and # comments)."""
    queries = []
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                queries.append(line)
    except FileNotFoundError:
        print(f"Warning: query file not found: {path}, skipping.")
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
    Category inference. Order matters — more specific checks first.
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
    if any(k in t for k in ["sleep music", "lofi", "lo-fi", "piano", "instrumental", "432hz", "singing bowls"]):
        return "music"
    if any(k in t for k in ["bedtime yoga", "gentle yoga", "stretch", "stretches", "lying down yoga"]):
        return "gentle_movement"
    # New categories
    if any(k in t for k in ["train window", "scenic", "slow tv", "aerial", "underwater", "scenic drive", "norway train", "japan countryside"]):
        return "scenic"
    if any(k in t for k in ["gratitude", "wind down", "end of day", "evening reflection", "nightly"]):
        return "wind_down"
    return "other"


def estimate_intensity(title: str, description: str) -> float:
    """
    Heuristic intensity score in [0,1]. Lower = calmer.

    Scoring logic:
    - Base: 0.35
    - Stacks multiple calming deductions so genuinely calm content scores low
    - New scenic/wind_down categories get a floor to keep them Stage A appropriate
    - Stimulating cues push score up
    """
    text = f"{title} {description}".lower()
    score = 0.35

    # Strong calming cues (each stacks)
    if any(k in text for k in ["white noise", "brown noise", "pink noise", "black screen"]):
        score -= 0.20
    if any(k in text for k in ["rain", "ocean", "waves", "fireplace", "thunder"]):
        score -= 0.15
    if any(k in text for k in ["asmr", "whisper", "soft spoken", "no talking"]):
        score -= 0.12
    if any(k in text for k in ["sleep", "bedtime", "fall asleep", "deep sleep"]):
        score -= 0.10
    if any(k in text for k in ["meditation", "body scan", "breathing", "guided"]):
        score -= 0.08
    if any(k in text for k in ["relax", "calm", "gentle", "soothing"]):
        score -= 0.05
    if any(k in text for k in ["lofi", "lo-fi", "432hz", "singing bowls", "ambient"]):
        score -= 0.08

    # Scenic / passive viewing: calm but engaging — floor at 0.18 (Stage A appropriate)
    if any(k in text for k in ["scenic", "train window", "slow tv", "aerial", "underwater", "norway", "japan countryside"]):
        score = max(score, 0.18)

    # Wind-down but not sleepy yet — floor at 0.20
    if any(k in text for k in ["gratitude", "wind down", "end of day", "evening", "nightly"]):
        score = max(score, 0.20)

    # Stimulating cues
    if any(k in text for k in ["true crime", "news", "debate", "politics"]):
        score += 0.40
    if any(k in text for k in ["comedy", "funny", "prank", "reaction"]):
        score += 0.25
    if any(k in text for k in ["morning", "energy", "wake up", "workout"]):
        score += 0.15

    return round(max(0.0, min(1.0, score)), 2)


# -------------------- Firestore --------------------

def get_firestore_client():
    """Initialize Firebase app (idempotent) and return Firestore client."""
    if not firebase_admin._apps:
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
    return firestore.client()


def upload_rows_to_firestore(rows: list[dict]) -> None:
    """
    Upsert rows into Firestore using the video's 'id' field as the document ID.
    Uses batched writes (max 500 ops per batch) to stay within Firestore limits.
    Skips documents that already exist so re-runs don't overwrite existing data.
    """
    db = get_firestore_client()
    collection = db.collection(FIRESTORE_COLLECTION)

    # Check which IDs already exist to avoid overwriting
    existing_ids = set()
    for doc in collection.select([]).stream():
        existing_ids.add(doc.id)

    new_rows = [r for r in rows if r["id"] not in existing_ids]
    skipped = len(rows) - len(new_rows)

    if skipped:
        print(f"Skipping {skipped} videos already in Firestore.")
    if not new_rows:
        print("No new videos to upload.")
        return

    BATCH_SIZE = 500
    total_written = 0

    for i in range(0, len(new_rows), BATCH_SIZE):
        batch = db.batch()
        chunk = new_rows[i:i + BATCH_SIZE]
        for row in chunk:
            doc_ref = collection.document(row["id"])
            batch.set(doc_ref, row)
        batch.commit()
        total_written += len(chunk)
        print(f"Committed batch: {total_written}/{len(new_rows)} new videos uploaded.")

    print(f"Done. {total_written} new videos added to Firestore '{FIRESTORE_COLLECTION}'.")


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


# -------------------- Main --------------------

def main():
    youtube = build_client()

    # 1) Load queries from all query files
    all_queries = []
    for path in QUERIES_PATHS:
        queries = read_queries(path)
        print(f"Loaded {len(queries)} queries from {path}")
        all_queries.extend(queries)
    print(f"Total queries: {len(all_queries)}")

    # 2) search.list per query -> collect candidate IDs + provenance
    id_to_query = {}
    for q in all_queries:
        ids = search_video_ids(youtube, q)
        print(f'Query "{q}" -> {len(ids)} non-live IDs')
        for vid in ids:
            if vid not in id_to_query:
                id_to_query[vid] = q

    print(f"Unique IDs after dedupe: {len(id_to_query)}")

    # 3) videos.list -> enrich + filter -> build rows
    rows = fetch_details(youtube, id_to_query)
    print(f"Final indexed rows (after filters): {len(rows)}")

    if not rows:
        print("No videos survived filtering (live/duration).")
        return

    # 4) Upload directly to Firestore (skips existing docs)
    upload_rows_to_firestore(rows)

    # 5) Write CSV backup for debugging/repro
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