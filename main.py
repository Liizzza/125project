"""
Sleep Coach API — FastAPI backend (v4.2)
Unified Version: Includes robust background extraction, multi-user support,
and strict filtering for Apple Health XML exports.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import json
import uuid
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from datetime import datetime, date
import pandas as pd
import time

# Firebase utilities (Assumed to be in firebase_utils.py)
import firebase_utils

# ── App setup ──────────────────────────────────────────────────────────────────
app = FastAPI(title="Sleep Coach API — Firestore Backend", version="4.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Directory layout ───────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
SCRIPT_DIR = BASE_DIR / "scripts"
# We use a persistent temp area for processing
TEMP_DIR = Path(tempfile.gettempdir()) / "sleep_coach"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT_NAMES = {
    "extract": "extract_sleep.py",
    "nightly": "build_sleep_nightly.py",
    "profile": "build_sleep_profile.py",
    "plan": "make_sleep_plan.py",
    "content": "recommend_content.py",
    "bundle": "run_tonight.py",
}

# ── Per-user helpers ───────────────────────────────────────────────────────────

def user_temp_dir(user_id: str) -> Path:
    d = TEMP_DIR / user_id
    d.mkdir(parents=True, exist_ok=True)
    return d

def user_temp_files(user_id: str) -> dict:
    d = user_temp_dir(user_id)
    return {
        "export_xml": d / "export.xml",
        "sleep_records": d / "sleep_records.csv",
        "sleep_nightly": d / "sleep_index_nightly.csv",
        "sleep_profile": d / "sleep_profile.json",
        "constraints": d / "tomorrow_constraints.json",
        "tonight_plan": d / "tonight_plan.json",
        "tonight_content": d / "tonight_content.json",
        "tonight_bundle": d / "tonight_bundle.json",
        "nap_log": d / "nap_log.json",
    }

def assert_user_exists_in_firestore(user_id: str):
    if not firebase_utils.user_exists_in_firestore(user_id):
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found.")

def verify_auth_header(authorization: Optional[str] = Header(None)) -> str:
    try:
        return firebase_utils.get_user_from_header(authorization)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

def run_script(script_name: str, user_id: str) -> dict:
    script_path = SCRIPT_DIR / script_name
    if not script_path.exists():
        raise HTTPException(status_code=500, detail=f"Script not found: {script_name}")
    
    env = os.environ.copy()
    env["USER_DATA_DIR"] = str(user_temp_dir(user_id))
    
    result = subprocess.run(
        ["python3", str(script_path)],
        capture_output=True, text=True,
        cwd=str(BASE_DIR), env=env,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }

def load_temp_json(path: Path) -> dict:
    if not path.exists(): return {}
    try:
        with open(path) as f: return json.load(f)
    except Exception: return {}

def load_temp_csv_as_json(path: Path) -> list:
    if not path.exists(): return []
    try:
        df = pd.read_csv(path)
        return json.loads(df.to_json(orient="records"))
    except Exception: return []

def fmt_time(mins: int) -> str:
    mins = int(mins) % 1440
    h, m = divmod(mins, 60)
    ampm = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {ampm}"

def time_str_to_min(t: Optional[str]) -> Optional[int]:
    if not t: return None
    try:
        h, m = map(int, t.strip().split(":"))
        return h * 60 + m
    except Exception:
        raise HTTPException(status_code=422, detail=f"Invalid time '{t}'. Use HH:MM (24h).")

# ── Pydantic models ────────────────────────────────────────────────────────────

class SleepPreferences(BaseModel):
    target_sleep_hours: Optional[float] = 8.0
    must_wake_by: Optional[str] = None
    preferred_wake_time: Optional[str] = None
    no_bed_after: Optional[str] = None
    min_sleep_opportunity_hours: Optional[float] = None
    avoid_high_intensity_near_bed: Optional[bool] = False
    caffeine_cutoff_time: Optional[str] = None
    preferred_categories: Optional[list] = None
    stage_a_categories: Optional[list] = None
    stage_b_categories: Optional[list] = None
    category_weights: Optional[dict] = None

class NapLog(BaseModel):
    duration_minutes: float
    nap_time: Optional[str] = None

# ── Background Worker ──────────────────────────────────────────────────────────

def process_extraction_task(user_id: str, zip_path: Path):
    temp_files = user_temp_files(user_id)
    firebase_utils.set_processing_status(user_id, "processing")
    
    try:
        def recursive_unzip(current_zip_path, target_output_path):
            with zipfile.ZipFile(current_zip_path, 'r') as z:
                candidates = [f for f in z.namelist() 
                            if f.lower().endswith(".xml") 
                            and not os.path.basename(f).startswith('.')
                            and "__macosx" not in f.lower()]
                
                if not candidates:
                    return False
                
                best_candidate = max(candidates, key=lambda x: z.getinfo(x).file_size)
                
                with z.open(best_candidate) as source, open(target_output_path, "wb") as target:
                    shutil.copyfileobj(source, target)
                
                # Check if what we just extracted is ANOTHER zip
                with open(target_output_path, "rb") as check_f:
                    header = check_f.read(4)
                    if header == b"PK\x03\x04":
                        print(f"🔄 Nested ZIP detected in {best_candidate}!")
                        # Create a unique temp name for the nested zip
                        nested_temp = target_output_path.parent / f"temp_{uuid.uuid4()}.zip"
                        target_output_path.rename(nested_temp)
                        
                        success = recursive_unzip(nested_temp, target_output_path)
                        
                        # SAFE DELETE: Only delete if it still exists
                        if nested_temp.exists():
                            nested_temp.unlink()
                        return success
                return True
        # Start the process
        if recursive_unzip(zip_path, temp_files["export_xml"]):
            print(f"📦 Final XML successfully prepared for {user_id}")
            
            # Run the extraction script
            result = run_script(SCRIPT_NAMES["extract"], user_id)
            
            if result["returncode"] == 0:
                records = load_temp_csv_as_json(temp_files["sleep_records"])
                firebase_utils.save_sleep_records_csv(user_id, records)
                firebase_utils.set_processing_status(user_id, "completed")
                print(f"✅ SUCCESS for {user_id}")
            else:
                print(f"❌ Script error: {result['stderr']}")
                firebase_utils.set_processing_status(user_id, "failed")
        else:
            print("❌ No XML found anywhere in the ZIP chain.")
            firebase_utils.set_processing_status(user_id, "failed")
            
    except Exception as e:
        print(f"❌ Worker error: {e}")
        firebase_utils.set_processing_status(user_id, "failed")
    finally:
        # Cleanup the initial upload
        if zip_path.exists(): zip_path.unlink()        # ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.post("/upload/health-data", status_code=201)
async def upload_health_data(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...),
    current_user: str = Depends(verify_auth_header)
):
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Please upload a .zip file.")

    user_id = current_user
    temp_dir = user_temp_dir(user_id)
    zip_path = temp_dir / f"{uuid.uuid4()}.zip" # Unique name to avoid collisions
    
    with open(zip_path, "wb") as out:
        shutil.copyfileobj(file.file, out)

    firebase_utils.create_firestore_user_doc(user_id)
    background_tasks.add_task(process_extraction_task, user_id, zip_path)

    return {"message": "Upload successful. Processing in background."}

@app.get("/users/{user_id}/status")
def get_status(user_id: str, current_user: str = Depends(verify_auth_header)):
    if user_id != current_user: raise HTTPException(status_code=403)
    return {"status": firebase_utils.get_processing_status(user_id)}

@app.post("/users/{user_id}/preferences")
def save_preferences(user_id: str, prefs: SleepPreferences, current_user: str = Depends(verify_auth_header)):
    if user_id != current_user: raise HTTPException(status_code=403)
    assert_user_exists_in_firestore(user_id)
    
    existing_profile = firebase_utils.get_sleep_profile(user_id)
    profile = {**existing_profile, "user_id": user_id, "target_sleep_min": int((prefs.target_sleep_hours or 8.0) * 60)}
    
    for field in ["preferred_categories", "stage_a_categories", "stage_b_categories"]:
        val = getattr(prefs, field)
        if val: profile[field] = val
        
    constraints = {
        "must_wake_by_min": time_str_to_min(prefs.must_wake_by),
        "preferred_wake_min": time_str_to_min(prefs.preferred_wake_time),
        "hard_constraints": {
            "no_bed_after_min": time_str_to_min(prefs.no_bed_after),
            "min_sleep_opportunity_min": int(prefs.min_sleep_opportunity_hours * 60) if prefs.min_sleep_opportunity_hours else None,
        },
        "soft_constraints": {
            "avoid_high_intensity_near_bed": prefs.avoid_high_intensity_near_bed or False,
            "caffeine_cutoff_min": time_str_to_min(prefs.caffeine_cutoff_time),
        },
    }

    firebase_utils.save_sleep_profile(user_id, profile)
    firebase_utils.save_user_constraints(user_id, constraints)
    return {"message": "Preferences saved."}

@app.post("/users/{user_id}/tonight/bundle")
def run_and_get_bundle(user_id: str, current_user: str = Depends(verify_auth_header)):
    if user_id != current_user: raise HTTPException(status_code=403)
    assert_user_exists_in_firestore(user_id)
    temp_files = user_temp_files(user_id)

    try:
        # Hydrate temp folder from Firestore
        records = firebase_utils.get_sleep_records_csv(user_id)
        if not records:
            raise HTTPException(status_code=400, detail="No sleep records found. Please upload health data first.")
        
        pd.DataFrame(records).to_csv(temp_files["sleep_records"], index=False)
        
        for key, func in [("sleep_profile", firebase_utils.get_sleep_profile), 
                         ("constraints", firebase_utils.get_user_constraints),
                         ("nap_log", firebase_utils.get_nap_log)]:
            with open(temp_files[key], "w") as f: json.dump(func(user_id), f)

        res = run_script(SCRIPT_NAMES["bundle"], user_id)
        if res["returncode"] != 0: raise HTTPException(status_code=500, detail=res["stderr"])
        
        data = load_temp_json(temp_files["tonight_bundle"])
        if "plan" in data:
            data["plan"]["bedtime_str"] = fmt_time(data["plan"].get("bedtime_min", 0))
            data["plan"]["wake_str"] = fmt_time(data["plan"].get("wake_min", 0))
        
        firebase_utils.save_tonight_bundle(user_id, data)
        return data
    finally:
        shutil.rmtree(user_temp_dir(user_id), ignore_errors=True)

@app.get("/users/{user_id}/tonight/bundle")
def get_bundle(user_id: str, current_user: str = Depends(verify_auth_header)):
    if user_id != current_user: raise HTTPException(status_code=403)
    data = firebase_utils.get_tonight_bundle(user_id)
    if not data: raise HTTPException(status_code=404)
    return data

@app.get("/users/{user_id}/sleep/history")
def get_sleep_history(user_id: str, days: int = 14, current_user: str = Depends(verify_auth_header)):
    if user_id != current_user: raise HTTPException(status_code=403)
    records = firebase_utils.get_sleep_nightly(user_id)
    if not records: return {"nights": []}
    df = pd.DataFrame(records).sort_values("sleep_date", errors="ignore").tail(days)
    return {"nights": json.loads(df.to_json(orient="records"))}
