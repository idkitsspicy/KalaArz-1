from flask import Flask, request, jsonify, render_template
import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

app = Flask(__name__, template_folder='templates')

# Get the API key from environment variables
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

@app.route('/')
def market():
    # Make sure this points to your HTML file inside the 'templates' folder
    return render_template('market.html')

@app.route('/generate-insights', methods=['POST'])
def generate_insights():
    if not GEMINI_KEY:
        return jsonify({"error": "GEMINI_KEY environment variable not found or is not set."}), 500

    data = request.json
    region = data.get("region")
    if not region:
        return jsonify({"error": "Region is required."}), 400

    system_prompt = """
You are an expert market research analyst specializing in Indian artisan crafts. 
Your goal is to provide **actionable, data-driven insights** for artisans to help them boost sales and plan for upcoming festive seasons. 
You must consider regional preferences, seasonal trends, and marketing opportunities. 
Provide the output strictly in the JSON format specified by the user. 
Assume today is September 19, 2025, and it is the peak festive season leading up to Dasara and Diwali. 
Focus on practical suggestions that local artisans can implement immediately.
"""
    user_query = f"""For the region of {region}, generate market insights for local artisans.
Provide your output strictly as a JSON object with the following keys:

{{
  "popular_crafts": [
    {{
      "craft_name": "Name of the craft",
      "description": "Short explanation of why this craft is popular in the region."
    }}
  ],
  "trending_products": [
    {{
      "product_type": "Specific product type",
      "reasoning": "Explanation of why this product is trending in the region now."
    }}
  ],
  "marketing_angle": "A clear marketing recommendation tailored for local artisans."
}}

Provide 2–4 popular crafts, 2–4 trending products, and a detailed marketing_angle.
Do not include any extra text outside the JSON object."""

    payload = {
        "contents": [{"parts": [{"text": user_query}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {"responseMimeType": "application/json"}
    }

    # CORRECTED: API key is passed as a query parameter in the URL.
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={GEMINI_KEY}"
    
    # The 'Authorization' header is not needed.
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # Raises an exception for bad status codes (4xx or 5xx)
        
        # Parse the response from Gemini and extract the actual content
        gemini_response = response.json()
        candidate = gemini_response.get("candidates", [{}])[0]
        content = candidate.get("content", {}).get("parts", [{}])[0]
        text_content = content.get("text", "{}")
        
        # Return the clean, parsed JSON content directly to the frontend
        return jsonify(json.loads(text_content))

    except requests.RequestException as e:
        error_message = f"Request failed: {str(e)}"
        if e.response is not None:
             error_message += f" | Response Body: {e.response.text}"
        return jsonify({"error": error_message}), 500
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        return jsonify({"error": f"Failed to parse Gemini response: {str(e)}"}), 502


if __name__ == "__main__":
    app.run(debug=True, port=5001)