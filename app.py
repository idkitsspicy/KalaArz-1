import os
import json
from flask import Flask, request, jsonify, render_template, g
import firebase_admin
from firebase_admin import credentials, auth
from flask_cors import CORS

app = Flask(__name__)
# Allow requests from your static site only
CORS(app, origins=["https://kalaarz-3.onrender.com"])
# Firebase Admin setup
if not firebase_admin._apps:
    cred_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    if not cred_json:
        raise RuntimeError("Set FIREBASE_SERVICE_ACCOUNT env variable")
    cred = credentials.Certificate(json.loads(cred_json))
    firebase_admin.initialize_app(cred)

def verify_firebase_token():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    id_token = auth_header.split("Bearer ")[1]
    try:
        decoded = auth.verify_id_token(id_token)
        g.user = decoded
        return decoded
    except Exception as e:
        print("Token verification failed:", e)
        return None

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/story")
def story_page():
    return render_template("story.html")

@app.route("/generate", methods=["POST"])
def generate():
    decoded = verify_firebase_token()
    if not decoded:
        return jsonify(ok=False, error="Unauthorized"), 401

    user_uid = decoded["uid"]
    data = request.get_json() or {}
    description = data.get("description", "")
    if not description:
        return jsonify(ok=False, error="No description provided"), 400

    # Example: simply echo back (replace with AI/Gemini call)
    story_text = f"Generated story for UID {user_uid}: {description}"

    return jsonify(ok=True, story=story_text)

@app.route("/publish", methods=["POST"])
def publish():
    decoded = verify_firebase_token()
    if not decoded:
        return jsonify(ok=False, error="Unauthorized"), 401

    user_uid = decoded["uid"]
    story_text = request.form.get("story", "")
    if not story_text:
        return jsonify(ok=False, error="No story provided"), 400

    # Save to file (or Firestore, S3, etc.)
    os.makedirs("stories", exist_ok=True)
    filename = f"{user_uid}.txt"
    with open(os.path.join("stories", filename), "w") as f:
        f.write(story_text)

    return jsonify(ok=True, story=story_text)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

