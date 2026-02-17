import firebase_admin
from firebase_admin import credentials, auth
import os

cred = credentials.Certificate("secrets/serviceAccountKey.json")
firebase_admin.initialize_app(cred)

def get_user_folder(id_token):
    try:
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        folder = f"users/{uid}/"
        os.makedirs(folder, exist_ok=True)
        return folder
    except Exception as e:
        print("Invalid token", e)
        return None
