import os
import math
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore

CSV_PATH = "data/video_index.csv"
SERVICE_ACCOUNT_PATH = "secrets/serviceAccountKey.json"
COLLECTION = "contentItems"

def clean_value(v):
    """Convert pandas/numpy values into plain Python types Firestore accepts."""
    if pd.isna(v):
        return None
    # Convert numpy scalars to python scalars
    if hasattr(v, "item"):
        return v.item()
    return v

def main():
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"Missing CSV: {CSV_PATH}")
    if not os.path.exists(SERVICE_ACCOUNT_PATH):
        raise FileNotFoundError(f"Missing service account JSON: {SERVICE_ACCOUNT_PATH}")

    # Init firebase once
    if not firebase_admin._apps:
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)

    db = firestore.client()

    df = pd.read_csv(CSV_PATH)

    # Ensure types are correct (important!)
    if "durationMin" in df.columns:
        df["durationMin"] = df["durationMin"].fillna(0).astype(int)
    if "intensity" in df.columns:
        df["intensity"] = df["intensity"].astype(float)

    if "id" not in df.columns:
        raise ValueError("CSV must contain an 'id' column to use as Firestore document IDs.")

    total = len(df)
    print(f"Uploading {total} rows from {CSV_PATH} into Firestore collection '{COLLECTION}'...")

    BATCH_SIZE = 450  # Firestore limit is 500 writes per batch
    num_batches = math.ceil(total / BATCH_SIZE)

    for b in range(num_batches):
        start = b * BATCH_SIZE
        end = min((b + 1) * BATCH_SIZE, total)

        batch = db.batch()
        for _, row in df.iloc[start:end].iterrows():
            doc_id = str(row["id"])  # e.g., youtube_eTeD8DAta4c
            doc_ref = db.collection(COLLECTION).document(doc_id)

            data = {col: clean_value(row[col]) for col in df.columns}
            data["updatedAt"] = firestore.SERVER_TIMESTAMP  # helpful debug field

            batch.set(doc_ref, data, merge=True)

        batch.commit()
        print(f"Committed batch {b+1}/{num_batches} (rows {start}..{end-1})")

    print("Done! ✅")

if __name__ == "__main__":
    main()
