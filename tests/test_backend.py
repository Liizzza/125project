import os
import requests
from dotenv import load_dotenv

load_dotenv()

def _load_firebase_api_key():
    key = os.getenv("FIREBASE_API_KEY")
    if key:
        return key.strip()
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "secrets", "firebase_web_api_key.txt"))
    if os.path.isfile(path):
        with open(path) as f:
            return f.read().strip()
    raise RuntimeError("FIREBASE_API_KEY not set")

# ================= CONFIG =================
# Get from Firebase Console → Project Settings → General → Web API Key
# Put in secrets/firebase_web_api_key.txt, or export FIREBASE_API_KEY, or .env
FIREBASE_API_KEY = _load_firebase_api_key()
EMAIL = "test@te.com"
PASSWORD = "person1234"

BACKEND_URL = "http://127.0.0.1:5001/run_sleep_plan"
# =========================================

def get_id_token(email, password, api_key):
    """Sign in the Firebase test user and get an ID token"""
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    response = requests.post(url, json=payload)
    if not response.ok:
        print("Firebase error:", response.text)
        response.raise_for_status()
    # #region agent log
    try:
        import json
        _log = {"location": "test_backend.py:get_id_token", "timestamp": __import__("time").time() * 1000}
        _log["message"] = "Firebase signIn response"
        _log["data"] = {"status": response.status_code, "body": response.text[:500]}
        with open("/Users/pavana/125project/.cursor/debug-051861.log", "a") as _f:
            _f.write(json.dumps(_log) + "\n")
    except Exception:
        pass
    # #endregion
    response.raise_for_status()
    return response.json()["idToken"]

def call_backend(id_token):
    """Send ID token to backend and return JSON response"""
    payload = {"idToken": id_token}
    response = requests.post(BACKEND_URL, json=payload)
    response.raise_for_status()
    return response.json()

def main():
    # #region agent log
    try:
        import json
        _path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "secrets", "firebase_web_api_key.txt"))
        _log = {"location": "test_backend.py:main", "timestamp": __import__("time").time() * 1000, "message": "Config check",
                "data": {"key_loaded": bool(FIREBASE_API_KEY and FIREBASE_API_KEY != "YOUR_WEB_API_KEY"),
                        "key_len": len(FIREBASE_API_KEY) if FIREBASE_API_KEY else 0,
                        "file_exists": os.path.isfile(_path), "resolved_path": _path}}
        with open("/Users/pavana/125project/.cursor/debug-051861.log", "a") as _f:
            _f.write(json.dumps(_log) + "\n")
    except Exception:
        pass
    # #endregion
    if not FIREBASE_API_KEY or FIREBASE_API_KEY == "YOUR_WEB_API_KEY":
        print("❌ FIREBASE_API_KEY is not set.")
        print("   Get it from: Firebase Console → Project Settings → General → Web API Key")
        print("   Put it in: secrets/firebase_web_api_key.txt")
        print("   Or run: export FIREBASE_API_KEY='your-key'")
        raise SystemExit(1)

    print("✅ Logging in Firebase test user...")
    id_token = get_id_token(EMAIL, PASSWORD, FIREBASE_API_KEY)
    print("✅ ID Token acquired!")

    print("✅ Calling backend endpoint...")
    result = call_backend(id_token)
    print("✅ Backend response:")
    print(result)

if __name__ == "__main__":
    main()
