import os
from flask import Flask, request, render_template, jsonify, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, auth
from flask_cors import CORS

# -------------------------------------------------------------------
# Flask app + rate limiter
# -------------------------------------------------------------------
app = Flask(__name__)
CORS(app)
limiter = Limiter(get_remote_address, app=app, default_limits=["20 per minute"])

# -------------------------------------------------------------------
# Firebase Admin setup (for token verification)
# -------------------------------------------------------------------
if not firebase_admin._apps:
    if os.getenv("FIREBASE_SERVICE_ACCOUNT"):
        cred_dict = json.loads(os.getenv("FIREBASE_SERVICE_ACCOUNT"))
        cred = credentials.Certificate(cred_dict)
    else:
        cred = credentials.Certificate("firebase-service-account.json")
    firebase_admin.initialize_app(cred)

# -------------------------------------------------------------------
# Gemini API setup
# -------------------------------------------------------------------
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

generation_config = {
    "temperature": 0.7,
    "top_p": 0.9,
    "top_k": 40,
    "max_output_tokens": 500,
    "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
)

# -------------------------------------------------------------------
# Firebase token verification helper
# -------------------------------------------------------------------
def verify_token(id_token):
    try:
        decoded = auth.verify_id_token(id_token)
        g.user = decoded
        return decoded
    except Exception as e:
        print("Token verification failed:", e)
        return None

# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/story")
def story_page():
    return render_template("story.html")

@app.route("/generate", methods=["POST"])

def generate():
    data = request.get_json()
    if "idToken" not in data:
        return jsonify(ok=False, error="Missing ID token"), 401

    decoded = verify_token(data["idToken"])
    if not decoded:
        return jsonify(ok=False, error="Unauthorized"), 401

    user_uid = decoded["uid"]
    prompt = data.get("prompt", "No prompt provided")

    # Here, you can call your AI/story generator
    story_text = f"This is a generated story for UID {user_uid} based on: {prompt}"

    return jsonify(ok=True, uid=user_uid, story=story_text)

# -------------------------------------------------------------------
# Run
# -------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

