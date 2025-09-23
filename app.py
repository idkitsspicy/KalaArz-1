import os
import re
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import google.generativeai as genai
from firebase_admin import credentials, initialize_app, firestore, storage

# ================== Setup ==================
load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")

# Firebase setup
cred = credentials.Certificate("firebase/store/firebase-service-account.json")
initialize_app(cred, {"storageBucket": "artisan-3b8d6.appspot.com"})
db = firestore.client()
bucket = storage.bucket()

# Rate limiter
limiter = Limiter(key_func=get_remote_address, app=app, default_limits=["200/hour", "10/minute"])

# Allowed image types
ALLOWED_EXT = {"png", "jpg", "jpeg", "webp"}
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

# Gemini setup
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
MODEL_NAME = "gemini-1.5-flash"

# ================== Helpers ==================
def craft_prompt(payload: dict) -> str:
    nm = payload.get("name","").strip()
    age = payload.get("age","")
    place = payload.get("place","").strip() or "India"
    product = payload.get("productName","").strip() or "A handmade item"
    craft_type = payload.get("craftType","").strip() or "craft"
    materials = payload.get("materials","").strip()
    inspiration = payload.get("inspiration","").strip()
    audience = payload.get("audience","").strip()
    tone = payload.get("tone","Warm & Personal")
    language = payload.get("language","English")

    prompt = f"""
You are ArtisanAI, a marketing copywriter for handmade crafts.
Return ONLY valid JSON (no commentary) with keys: "story", "tags".
- story: 200-500 words in {language}, tone: {tone}.
- tags: list of 5 short social media tags for social media reach.

Inputs:
name="{nm}"
age="{age}"
place="{place}"
productName="{product}"
craftType="{craft_type}"
materials="{materials}"
inspiration="{inspiration}"
targetAudience="{audience}"
"""
    return prompt.strip()

def extract_json_from_text(text: str):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    s = text.find("{")
    e = text.rfind("}")
    if s != -1 and e != -1:
        candidate = text[s:e+1]
        try:
            return json.loads(candidate)
        except Exception:
            candidate_fixed = re.sub(r",\s*}", "}", re.sub(r",\s*]", "]", candidate))
            try:
                return json.loads(candidate_fixed)
            except Exception:
                return None
    try:
        return json.loads(text)
    except Exception:
        return None

# ================== Routes ==================
@app.route("/")
def login():
    return render_template("login.html")

@app.route("/story")
def story_page():
    uid = request.args.get("uid")
    if not uid:
        return "No UID provided. Please login first.", 403
    return render_template("story.html", uid=uid)

# ----- AI Story Generation -----
@app.route("/generate", methods=["POST"])
@limiter.limit("8/minute; 80/hour")
def generate_story():
    if not GEMINI_API_KEY:
        return jsonify(ok=False, error="Server not configured with GEMINI_API_KEY"), 500
    payload = request.get_json(force=True, silent=True) or {}
    prompt = craft_prompt(payload)
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        resp = model.generate_content(prompt)
        text = getattr(resp, "text", None)
        if not text and hasattr(resp, "candidates") and resp.candidates:
            text = resp.candidates[0].content.parts[0].text
        if not text:
            return jsonify(ok=False, error="Empty response from model"), 502
        parsed = extract_json_from_text(text)
        if not parsed:
            return jsonify(ok=False, error="Could not parse model output", raw=text), 502
        return jsonify(ok=True,
                       story=parsed.get("story", "").strip(),
                       tags=[str(t).strip() for t in parsed.get("tags", [])][:5])
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500

# ----- Publish Story -----
@app.route("/publish", methods=["POST"])
def publish_story():
    uid = request.form.get("uid")
    name = request.form.get("name", "").strip()
    age = request.form.get("age", "")
    place = request.form.get("place", "").strip()
    product_name = request.form.get("productName", "").strip()
    story = request.form.get("story", "").strip()
    tags_raw = request.form.get("tags", "")
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()][:5]

    if not uid or not product_name or not story or not name or not place or not age:
        return jsonify(ok=False, error="Missing required fields"), 400

    image_url = None
    file = request.files.get("image")
    if file and file.filename:
        if not allowed_file(file.filename):
            return jsonify(ok=False, error="Unsupported image type"), 400
        unique_name = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
        blob = bucket.blob(unique_name)
        blob.upload_from_file(file, content_type=file.content_type)
        blob.make_public()
        image_url = blob.public_url

    record = {
        "id": datetime.utcnow().strftime("%Y%m%d%H%M%S%f"),
        "uid": uid,
        "name": name,
        "age": age,
        "place": place,
        "productName": product_name,
        "story": story,
        "tags": tags,
        "image": image_url,
        "createdAt": datetime.utcnow().isoformat() + "Z",
    }

    try:
        db.collection("posts").document(record["id"]).set(record)
        return jsonify(ok=True, post=record)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500

# ----- Get All Posts -----
@app.route("/posts", methods=["GET"])
def get_posts():
    try:
        # Fetch all posts from Firestore, order by createdAt descending
        posts_ref = db.collection("posts").order_by("createdAt", direction=firestore.Query.DESCENDING)
        posts = [doc.to_dict() for doc in posts_ref.stream()]
        return jsonify(ok=True, posts=posts)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500

# ================== Run ==================
if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
