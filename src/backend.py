from flask import Flask, request, jsonify
import os 
import sys 
#so that it can find scripts 
from scripts.backend_utils import get_user_folder
import subprocess  # to run scripts 

app = Flask(__name__)


@app.route("/run_sleep_plan", methods=["POST"])
def run_sleep_plan():
    id_token = request.json.get("idToken")
    user_folder = get_user_folder(id_token)
    if not user_folder:
        return jsonify({"error": "Unauthorized"}), 401

    # Run your scripts for this user
    subprocess.run(["python", "extract_sleep.py", user_folder])
    subprocess.run(["python", "build_sleep_profile.py", user_folder])
    subprocess.run(["python", "make_sleep_plan.py", user_folder])

    return jsonify({"status": "success", "message": f"Sleep plan generated for {user_folder}"})
