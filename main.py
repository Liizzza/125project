"""
Sleep Coach API — FastAPI backend (multi-user, v3)
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import json
import uuid
import subprocess
import shutil
import os
from pathlib import Path
from datetime import datetime, date
import pandas as pd

# ── App setup ──────────────────────────────────────────────────────────────────
app = FastAPI(title="Sleep Coach API — Multi-User", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Directory layout ───────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
USERS_DIR  = BASE_DIR / "data" / "users"
SCRIPT_DIR = BASE_DIR / "scripts"
USERS_DIR.mkdir(parents=True, exist_ok=True)

SCRIPT_NAMES = {
    "extract": "extract_sleep.py",
    "nightly": "build_sleep_nightly.py",
    "profile":  "build_sleep_profile.py",
    "plan":     "make_sleep_plan.py",
    "content":  "recommend_content.py",
    "bundle":   "run_tonight.py",
}

# ── Per-user helpers ───────────────────────────────────────────────────────────

def user_dir(user_id: str) -> Path:
    d = USERS_DIR / user_id
    d.mkdir(parents=True, exist_ok=True)
    return d

def user_files(user_id: str) -> dict:
    d = user_dir(user_id)
    return {
        "export_xml":      d / "export.xml",
        "sleep_records":   d / "sleep_records.csv",
        "sleep_nightly":   d / "sleep_index_nightly.csv",
        "sleep_profile":   d / "sleep_profile.json",
        "constraints":     d / "tomorrow_constraints.json",
        "tonight_plan":    d / "tonight_plan.json",
        "tonight_content": d / "tonight_content.json",
        "tonight_bundle":  d / "tonight_bundle.json",
        "nap_log":         d / "nap_log.json",
    }

def assert_user_exists(user_id: str):
    if not (USERS_DIR / user_id).exists():
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found.")

def run_script(script_name: str, user_id: str) -> dict:
    script_path = SCRIPT_DIR / script_name
    if not script_path.exists():
        raise HTTPException(status_code=500, detail=f"Script not found: {script_name}")
    env = os.environ.copy()
    env["USER_DATA_DIR"] = str(user_dir(user_id))
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

def load_json_file(path: Path) -> dict:
    if not path.exists():
        raise HTTPException(status_code=404,
            detail=f"'{path.name}' not found. Run the pipeline first.")
    with open(path) as f:
        return json.load(f)

def fmt_time(mins: int) -> str:
    mins = int(mins) % 1440
    h, m = divmod(mins, 60)
    ampm = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {ampm}"

def time_str_to_min(t: Optional[str]) -> Optional[int]:
    if not t:
        return None
    try:
        h, m = map(int, t.strip().split(":"))
        return h * 60 + m
    except Exception:
        raise HTTPException(status_code=422, detail=f"Invalid time '{t}'. Use HH:MM (24h).")

def enrich_bundle(data: dict, user_id: str) -> dict:
    """
    Inject all fields the Swift app expects but that run_tonight.py
    may not write: bedtime_str, wake_str, quality label, stage windows.
    """
    # ── Plan: human-readable times + quality label ─────────────────────────
    if "plan" in data:
        plan = data["plan"]
        if "bedtime_str" not in plan:
            plan["bedtime_str"] = fmt_time(plan.get("bedtime_min", 0))
        if "wake_str" not in plan:
            plan["wake_str"] = fmt_time(plan.get("wake_min", 0))

        # Quality label — compute here if not already set by make_sleep_plan.py
        if "quality_label" not in plan:
            debt  = float(plan.get("debt_min", 0))
            score = float(plan.get("score", 0))
            plan["quality_label"], plan["quality_subtitle"], plan["quality_color"] = \
                quality_label(score, debt)

    # ── Stages: inject window strings ─────────────────────────────────────
    if "stages" in data:
        stages = data["stages"]
        now_min     = int(stages.get("now_min", 0))
        bedtime_min = int(stages.get("bedtime_min", 0))
        wake_min    = int(stages.get("wake_min", 0))

        mins_until_bed = (bedtime_min - now_min) % 1440
        stage_b_start  = max(0, mins_until_bed - 45)

        # Stage A window: now → 45 min before bed
        if stage_b_start > 0:
            stage_a_window = f"Now → {fmt_time((now_min + stage_b_start) % 1440)}"
        else:
            stage_a_window = "Wind-down time"

        # Stage B window: last 45 min before bed
        stage_b_window = f"{fmt_time((bedtime_min - 45) % 1440)} → {fmt_time(bedtime_min)}"

        if "stage_a" in stages:
            stages["stage_a"]["label"] = "Wind Down"
            stages["stage_a"]["window"] = stage_a_window
        if "stage_b" in stages:
            stages["stage_b"]["label"] = "Lights Out"
            stages["stage_b"]["window"] = stage_b_window

    data["user_id"] = user_id
    return data


def quality_label(score: float, debt_min: float) -> tuple:
    """Returns (label, subtitle, color_hex)."""
    if debt_min < 60:
        if score >= 3.5:
            return ("Well Rested",     "Your sleep is on track",             "22C55E")
        elif score >= 2.5:
            return ("On Track",        "Solid sleep tonight",                "286EF1")
        else:
            return ("Fair",            "Could improve consistency",          "F59E0B")
    elif debt_min < 300:
        if score >= 3.0:
            return ("Recovering",      "Good plan to catch up",              "286EF1")
        else:
            return ("Slightly Behind", "Try to hit your bedtime tonight",    "F59E0B")
    elif debt_min < 600:
        return     ("Catch-Up Needed", "Prioritize sleep this week",         "F59E0B")
    else:
        return     ("High Debt",       "Focus on consistent early bedtimes", "EF4444")


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


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/users")
def list_users():
    ids = [d.name for d in USERS_DIR.iterdir() if d.is_dir()]
    return {"user_count": len(ids), "user_ids": sorted(ids)}


# ── Upload ─────────────────────────────────────────────────────────────────────

@app.post("/upload/health-data", status_code=201)
async def upload_health_data(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".xml"):
        raise HTTPException(status_code=400, detail="Please upload an Apple Health export.xml file.")

    user_id = str(uuid.uuid4())
    files = user_files(user_id)

    with open(files["export_xml"], "wb") as out:
        shutil.copyfileobj(file.file, out)

    result = run_script(SCRIPT_NAMES["extract"], user_id)
    if result["returncode"] != 0:
        shutil.rmtree(user_dir(user_id), ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {result['stderr']}")

    return {
        "user_id": user_id,
        "message": "Health data uploaded and sleep records extracted.",
        "next_step": f"POST /users/{user_id}/preferences  →  POST /users/{user_id}/tonight/bundle",
    }


# ── Preferences ────────────────────────────────────────────────────────────────

@app.post("/users/{user_id}/preferences")
def save_preferences(user_id: str, prefs: SleepPreferences):
    assert_user_exists(user_id)
    files = user_files(user_id)

    existing_profile = {}
    if files["sleep_profile"].exists():
        try:
            existing_profile = json.loads(files["sleep_profile"].read_text())
        except Exception:
            pass

    profile = {
        **existing_profile,
        "user_id": user_id,
        "target_sleep_min": int((prefs.target_sleep_hours or 8.0) * 60),
    }
    if prefs.preferred_categories:
        profile["preferred_categories"] = prefs.preferred_categories
    if prefs.stage_a_categories:
        profile["stage_a_categories"] = prefs.stage_a_categories
    if prefs.stage_b_categories:
        profile["stage_b_categories"] = prefs.stage_b_categories
    if prefs.category_weights:
        profile["category_weights"] = {
            k: max(0.0, min(2.0, float(v)))
            for k, v in prefs.category_weights.items()
        }

    constraints = {
        "must_wake_by_min":    time_str_to_min(prefs.must_wake_by),
        "preferred_wake_min":  time_str_to_min(prefs.preferred_wake_time),
        "hard_constraints": {
            "no_bed_after_min":          time_str_to_min(prefs.no_bed_after),
            "min_sleep_opportunity_min": (
                int(prefs.min_sleep_opportunity_hours * 60)
                if prefs.min_sleep_opportunity_hours else None
            ),
        },
        "soft_constraints": {
            "avoid_high_intensity_near_bed": prefs.avoid_high_intensity_near_bed or False,
            "caffeine_cutoff_min":           time_str_to_min(prefs.caffeine_cutoff_time),
        },
    }

    with open(files["sleep_profile"], "w") as f:
        json.dump(profile, f, indent=2)
    with open(files["constraints"], "w") as f:
        json.dump(constraints, f, indent=2)

    return {
        "message": "Preferences saved.",
        "user_id": user_id,
        "sleep_profile": profile,
        "constraints": constraints,
    }


# ── Nap logging ────────────────────────────────────────────────────────────────

@app.post("/users/{user_id}/nap")
def log_nap(user_id: str, nap: NapLog):
    assert_user_exists(user_id)

    if nap.duration_minutes <= 0 or nap.duration_minutes > 240:
        raise HTTPException(status_code=422,
            detail="duration_minutes must be between 1 and 240.")

    entry = {
        "date":             date.today().isoformat(),
        "duration_minutes": nap.duration_minutes,
        "nap_time":         nap.nap_time,
        "logged_at":        datetime.now().isoformat(),
    }

    with open(user_files(user_id)["nap_log"], "w") as f:
        json.dump(entry, f, indent=2)

    return {
        "message": f"Nap of {nap.duration_minutes} min logged. "
                   f"Tonight's sleep debt will be reduced by this amount.",
        "nap": entry,
    }


@app.get("/users/{user_id}/nap")
def get_nap(user_id: str):
    assert_user_exists(user_id)
    nap_path = user_files(user_id)["nap_log"]

    if not nap_path.exists():
        return {"message": "No nap logged today.", "nap": None}

    entry = json.loads(nap_path.read_text())
    if entry.get("date") != date.today().isoformat():
        return {"message": "No nap logged today (last log was a previous day).", "nap": None}

    return {"nap": entry}


# ── Pipeline ───────────────────────────────────────────────────────────────────

@app.post("/users/{user_id}/run/pipeline")
def run_pipeline(user_id: str):
    assert_user_exists(user_id)

    steps = [
        ("nightly index",           "nightly"),
        ("sleep profile",           "profile"),
        ("tonight's plan",          "plan"),
        ("content recommendations", "content"),
    ]

    results = []
    for label, key in steps:
        res = run_script(SCRIPT_NAMES[key], user_id)
        results.append({
            "step":    label,
            "success": res["returncode"] == 0,
            "output":  res["stdout"] or res["stderr"],
        })
        if res["returncode"] != 0:
            raise HTTPException(status_code=500,
                detail=f"Pipeline failed at '{label}': {res['stderr']}")

    return {
        "message":   "Pipeline completed successfully.",
        "user_id":   user_id,
        "steps":     results,
        "timestamp": datetime.now().isoformat(),
    }


# ── Read endpoints ─────────────────────────────────────────────────────────────

@app.get("/users/{user_id}/sleep/plan")
def get_sleep_plan(user_id: str):
    assert_user_exists(user_id)
    plan = load_json_file(user_files(user_id)["tonight_plan"])
    plan["bedtime_str"] = fmt_time(plan.get("bedtime_min", 0))
    plan["wake_str"]    = fmt_time(plan.get("wake_min", 0))
    return plan


@app.get("/users/{user_id}/sleep/profile")
def get_sleep_profile(user_id: str):
    assert_user_exists(user_id)
    return load_json_file(user_files(user_id)["sleep_profile"])


@app.get("/users/{user_id}/sleep/history")
def get_sleep_history(user_id: str, days: int = 14):
    assert_user_exists(user_id)
    path = user_files(user_id)["sleep_nightly"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="No nightly data yet. Run the pipeline first.")
    df = pd.read_csv(path).sort_values("sleep_date").tail(days)
    return {
        "user_id": user_id,
        "nights":  json.loads(df.where(df.notna(), other=None).to_json(orient="records")),
    }


@app.get("/users/{user_id}/content/recommendations")
def get_content_recommendations(user_id: str, limit: int = 10):
    assert_user_exists(user_id)
    data = load_json_file(user_files(user_id)["tonight_content"])
    return {
        "user_id":         user_id,
        "generated_at":    data.get("generated_at"),
        "context":         data.get("context"),
        "recommendations": data.get("recommendations", [])[:limit],
    }


# ── Bundle endpoints ───────────────────────────────────────────────────────────

@app.post("/users/{user_id}/tonight/bundle")
def run_and_get_bundle(user_id: str):
    """Run pipeline + return full enriched bundle."""
    assert_user_exists(user_id)
    res = run_script(SCRIPT_NAMES["bundle"], user_id)
    if res["returncode"] != 0:
        raise HTTPException(status_code=500, detail=f"Bundle failed: {res['stderr']}")
    data = load_json_file(user_files(user_id)["tonight_bundle"])
    return enrich_bundle(data, user_id)


@app.get("/users/{user_id}/tonight/bundle")
def get_bundle(user_id: str):
    """Return last generated bundle without re-running pipeline."""
    assert_user_exists(user_id)
    data = load_json_file(user_files(user_id)["tonight_bundle"])
    return enrich_bundle(data, user_id)