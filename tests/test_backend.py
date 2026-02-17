import requests

# ================= CONFIG =================
FIREBASE_API_KEY = "YOUR_WEB_API_KEY"  # Firebase Console → Project Settings → General
EMAIL = "test@te.com"
PASSWORD = "1231231231"

BACKEND_URL = "http://127.0.0.1:5000/run_sleep_plan"
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
    response.raise_for_status()
    return response.json()["idToken"]

def call_backend(id_token):
    """Send ID token to backend and return JSON response"""
    payload = {"idToken": id_token}
    response = requests.post(BACKEND_URL, json=payload)
    response.raise_for_status()
    return response.json()

def main():
    print("✅ Logging in Firebase test user...")
    id_token = get_id_token(EMAIL, PASSWORD, FIREBASE_API_KEY)
    print("✅ ID Token acquired!")

    print("✅ Calling backend endpoint...")
    result = call_backend(id_token)
    print("✅ Backend response:")
    print(result)

if __name__ == "__main__":
    main()
