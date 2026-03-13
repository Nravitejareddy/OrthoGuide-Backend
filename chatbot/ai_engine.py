import google.generativeai as genai
from config import Config

# Configure Gemini
genai.configure(api_key=Config.GEMINI_API_KEY)

# Load model
model = genai.GenerativeModel("gemini-1.5-flash")

def ask_ai(user_message):
    try:
        prompt = f"""
You are an orthodontic assistant helping patients wearing braces and aligners.

Rules:
- Give safe dental advice
- Keep answers short (2-4 sentences)
- If unsure, suggest contacting a clinician

Patient question: {user_message}
"""

        response = model.generate_content(prompt)

        # Debug log (helps verify AI response)
        print("Gemini raw response:", response)

        if response and hasattr(response, "text") and response.text:
            return response.text.strip()

    except Exception as e:
        print("Gemini API Error:", e)

    return None