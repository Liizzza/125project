"""
Firebase utilities for Sleep Coach API — COMPLETE VERSION
Includes all original functions plus Background Task Status tracking.
"""

import firebase_admin
from firebase_admin import credentials, auth, firestore
from pathlib import Path
import json
from datetime import datetime
from typing import Optional, Dict, Any
import os

# ── Initialization ─────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
SECRETS_DIR = BASE_DIR / "secrets"

_cred_path = SECRETS_DIR / "serviceAccountKey.json"
if not _cred_path.exists():
    raise FileNotFoundError(f"Firebase credentials not found at {_cred_path}")

cred = credentials.Certificate(str(_cred_path))

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ── Authentication ────────────────────────────────────────────────────────────

def verify_id_token(token: str) -> str:
    try:
        decoded = auth.verify_id_token(token)
        return decoded['uid']
    except Exception as e:
        raise ValueError(f"Invalid Firebase token: {str(e)}")

def get_user_from_header(authorization: Optional[str]) -> str:
    if not authorization:
        raise ValueError("Missing authorization header")
    try:
        parts = authorization.split(" ")
        if len(parts) != 2 or parts[0] != "Bearer":
            raise ValueError("Invalid authorization format.")
        token = parts[1]
        return verify_id_token(token)
    except Exception as e:
        raise ValueError(f"Auth error: {str(e)}")

# ── Processing Status (Added for v4.1 Background Support) ─────────────────────

def set_processing_status(user_id: str, status: str):
    """Updates status: 'processing', 'completed', or 'failed'"""
    db.collection("users").document(user_id).collection("data").document("status").set({
        "status": status,
        "updated_at": datetime.now(),
    })

def get_processing_status(user_id: str) -> str:
    doc = db.collection("users").document(user_id).collection("data").document("status").get()
    return doc.to_dict().get("status", "unknown") if doc.exists else "not_started"

# ── Firestore User Data Operations ─────────────────────────────────────────────

def create_firestore_user_doc(user_id: str, email: Optional[str] = None):
    user_data = {"user_id": user_id, "created_at": datetime.now(), "email": email}
    db.collection("users").document(user_id).set(user_data, merge=True)

def user_exists_in_firestore(user_id: str) -> bool:
    doc = db.collection("users").document(user_id).get()
    return doc.exists

def get_all_users() -> list:
    docs = db.collection("users").stream()
    return [doc.id for doc in docs]

# ── Preferences & Constraints ──────────────────────────────────────────────────

def save_user_preferences(user_id: str, preferences: dict):
    doc_data = {**preferences, "updated_at": datetime.now()}
    db.collection("users").document(user_id).collection("settings").document("preferences").set(doc_data)

def get_user_preferences(user_id: str) -> dict:
    doc = db.collection("users").document(user_id).collection("settings").document("preferences").get()
    if not doc.exists: return {}
    data = doc.to_dict() or {}
    return {k: v for k, v in data.items() if k != "updated_at"}

def save_user_constraints(user_id: str, constraints: dict):
    doc_data = {**constraints, "updated_at": datetime.now()}
    db.collection("users").document(user_id).collection("settings").document("constraints").set(doc_data)

def get_user_constraints(user_id: str) -> dict:
    doc = db.collection("users").document(user_id).collection("settings").document("constraints").get()
    if not doc.exists: return {}
    data = doc.to_dict() or {}
    return {k: v for k, v in data.items() if k != "updated_at"}

# ── Sleep Profile & Analysis Data ─────────────────────────────────────────────

def save_sleep_profile(user_id: str, profile: dict):
    doc_data = {**profile, "updated_at": datetime.now()}
    db.collection("users").document(user_id).collection("data").document("sleep_profile").set(doc_data)

def get_sleep_profile(user_id: str) -> dict:
    doc = db.collection("users").document(user_id).collection("data").document("sleep_profile").get()
    if not doc.exists: return {}
    data = doc.to_dict() or {}
    return {k: v for k, v in data.items() if k != "updated_at"}

def save_sleep_nightly(user_id: str, nightly_data: list):
    db.collection("users").document(user_id).collection("data").document("sleep_nightly").set({
        "records": nightly_data, "updated_at": datetime.now(),
    })

def get_sleep_nightly(user_id: str) -> list:
    doc = db.collection("users").document(user_id).collection("data").document("sleep_nightly").get()
    return doc.to_dict().get("records", []) if doc.exists else []

def save_sleep_plan(user_id: str, plan: dict):
    doc_data = {**plan, "generated_at": datetime.now()}
    db.collection("users").document(user_id).collection("data").document("sleep_plan").set(doc_data)

def get_sleep_plan(user_id: str) -> dict:
    doc = db.collection("users").document(user_id).collection("data").document("sleep_plan").get()
    if not doc.exists: return {}
    data = doc.to_dict() or {}
    return {k: v for k, v in data.items() if k != "generated_at"}

def save_content_recommendations(user_id: str, recommendations: dict):
    doc_data = {**recommendations, "generated_at": datetime.now()}
    db.collection("users").document(user_id).collection("data").document("content_recommendations").set(doc_data)

def get_content_recommendations(user_id: str) -> dict:
    doc = db.collection("users").document(user_id).collection("data").document("content_recommendations").get()
    if not doc.exists: return {}
    data = doc.to_dict() or {}
    return {k: v for k, v in data.items() if k != "generated_at"}

def save_tonight_bundle(user_id: str, bundle: dict):
    doc_data = {**bundle, "generated_at": datetime.now()}
    db.collection("users").document(user_id).collection("data").document("tonight_bundle").set(doc_data)

def get_tonight_bundle(user_id: str) -> dict:
    doc = db.collection("users").document(user_id).collection("data").document("tonight_bundle").get()
    if not doc.exists: return {}
    data = doc.to_dict() or {}
    return {k: v for k, v in data.items() if k != "generated_at"}

# ── Nap Logging ────────────────────────────────────────────────────────────────

def save_nap_log(user_id: str, nap_entry: dict):
    doc_data = {**nap_entry, "logged_at": datetime.now()}
    db.collection("users").document(user_id).collection("data").document("nap_log").set(doc_data)

def get_nap_log(user_id: str) -> dict:
    doc = db.collection("users").document(user_id).collection("data").document("nap_log").get()
    if not doc.exists: return {}
    data = doc.to_dict() or {}
    return {k: v for k, v in data.items() if k != "logged_at"}

# ── Health Data (Optimized for Large ZIPs) ────────────────────────────────────

def save_health_export_xml(user_id: str, xml_content: str):
    """NO LONGER USED: Kept for compatibility but does nothing to prevent Firestore 1MB crash."""
    pass

def get_health_export_xml(user_id: str) -> Optional[str]:
    """Retrieves raw XML if it exists (Likely will return None for new users)."""
    try:
        doc = db.collection("users").document(user_id).collection("data").document("health_export").get()
        return doc.to_dict().get("xml") if doc.exists else None
    except: return None

# ── Sleep Records ─────────────────────────────────────────────────────────────

def save_sleep_records_csv(user_id: str, csv_data: list):
    db.collection("users").document(user_id).collection("data").document("sleep_records").set({
        "records": csv_data, "updated_at": datetime.now(),
    })

def get_sleep_records_csv(user_id: str) -> list:
    doc = db.collection("users").document(user_id).collection("data").document("sleep_records").get()
    return doc.to_dict().get("records", []) if doc.exists else []
