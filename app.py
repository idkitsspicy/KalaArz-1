import os
import json
import re
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import google.generativeai as genai

# ================== Setup ==================
load_dotenv()
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = BASE_DIR / "static" / "uploads"
POSTS_FILE = DATA_DIR / "posts.json"
DATA_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
if not POSTS_FILE.exists():
    POSTS_FILE.write_text("[]", encoding="utf-8")

ALLOWED_EXT = {"png", "jpg", "jpeg", "webp"}
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 5 * 1024 * 1024))

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["UPLOAD_FOLDER"] = str(UPLOADS_DIR)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# Rate limiter
limiter = Limiter(key_func=get_remote_address, app=app, default_limits=["200/hour", "10/minute"])

# Gemini setup
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

MODEL_NAME = "gemini-1.5-flash"

# ================== Helpers ==================
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

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

        return jsonify(
            ok=True,
            story=parsed.get("story", "").strip(),
            tags=[str(t).strip() for t in parsed.get("tags", [])][:5],
        )
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500

# ----- Publish Story -----
@app.route("/publish", methods=["POST"])
@limiter.limit("20/hour")
def publish_story():
    name = request.form.get("name","").strip()
    age = request.form.get("age","")
    place = request.form.get("place","").strip()
    product_name = request.form.get("productName","").strip()
    story = request.form.get("story","").strip()
    tags_raw = request.form.get("tags","")
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()][:5]

    if not product_name or not story or not name or not place or not age:
        return jsonify(ok=False, error="Missing required fields"), 400

    image_url = None
    file = request.files.get("image")
    if file and file.filename:
        filename = secure_filename(file.filename)
        if not allowed_file(filename):
            return jsonify(ok=False, error="Unsupported image type"), 400
        saved = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{filename}"
        file.save(UPLOADS_DIR / saved)
        image_url = url_for("static", filename=f"uploads/{saved}")

    record = {
        "id": datetime.utcnow().strftime("%Y%m%d%H%M%S%f"),
        "productName": product_name,
        "story": story,
        "tags": tags,
        "image": image_url,
        "createdAt": datetime.utcnow().isoformat() + "Z",
    }

    try:
        posts = json.loads(POSTS_FILE.read_text(encoding="utf-8"))
        posts.insert(0, record)
        POSTS_FILE.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")
        return jsonify(ok=True, post=record)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500

# ----- Get All Posts -----
@app.route("/posts", methods=["GET"])
def get_posts():
    try:
        posts = json.loads(POSTS_FILE.read_text(encoding="utf-8"))
        return jsonify(ok=True, posts=posts)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500

# ================== Run ==================
if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)

