import os
from flask import Flask, request, render_template, jsonify, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, auth

# -------------------------------------------------------------------
# Flask app + rate limiter
# -------------------------------------------------------------------
app = Flask(__name__)
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
def verify_firebase_token():
    auth_header = request.headers.get("Authorization", None)
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    id_token = auth_header.split("Bearer ")[1]
    try:
        decoded = auth.verify_id_token(id_token)
        g.user = decoded  # store user globally in request context
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
def generate_story():
    decoded = verify_firebase_token()
    if not decoded:
        return jsonify(ok=False, error="Unauthorized"), 401

    user_uid = decoded["uid"]
    print("Generating story for UID:", user_uid)

    data = request.get_json() or {}
    description = data.get("prompt") or data.get("description")
    if not description:
        return jsonify(ok=False, error="No description provided"), 400

    prompt = f"Write a short engaging story based on: {description}"
    response = model.generate_content(prompt)
    story_text = response.text.strip() if response and response.text else "No story generated."

    return jsonify(ok=True, story=story_text)

# -------------------------------------------------------------------
# Run
# -------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
