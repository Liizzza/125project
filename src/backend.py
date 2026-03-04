from flask import Flask, request, jsonify
import os 
import sys 
#so that it can find scripts 
from scripts.backend_utils import get_user_folder
import subprocess  # to run scripts 

from flask_cors import CORS
app = Flask(__name__)
CORS(app)


@app.route("/run_sleep_plan", methods=["POST"])
def run_sleep_plan():
    data = request.get_json()

    if not data or "idToken" not in data:
        return jsonify({"error": "Missing idToken"}), 400

    id_token = data["idToken"]

    user_folder = get_user_folder(id_token)
    if not user_folder:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        # Use capture_output=True to grab the actual error message from the script
        result = subprocess.run(
            [sys.executable, "scripts/extract_sleep.py", user_folder],
            capture_output=True,
            text=True,
            check=True
        )
        
        # If the first one passes, run the others (simplified for now to find the bug)
        subprocess.run([sys.executable, "scripts/build_sleep_nightly.py", user_folder], check=True)
        subprocess.run([sys.executable, "scripts/build_sleep_profile.py", user_folder], check=True)
        subprocess.run([sys.executable, "scripts/make_sleep_plan.py", user_folder], check=True)

        return jsonify({"status": "success", "message": f"Generated for {user_folder}"})

    except subprocess.CalledProcessError as e:
        # This is the gold mine: it tells us what the script actually complained about
        error_message = e.stderr if e.stderr else str(e)
        print(f"❌ SCRIPT ERROR: {error_message}")
        return jsonify({
            "error": "Script failed",
            "script": e.cmd[1],
            "details": error_message
        }), 500
    except Exception as e:
        print(f"❌ GENERAL ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500
    
if __name__ == "__main__":
    # Use port 5001 because macOS often steals port 5000 for AirPlay
    app.run(host="127.0.0.1", port=5001, debug=True)
