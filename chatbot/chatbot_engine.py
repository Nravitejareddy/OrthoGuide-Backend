import json
import os
from difflib import SequenceMatcher
from typing import List, Dict
import re

faq_file = os.path.join(os.path.dirname(__file__), "orthodontic_faqs.json")

try:
    with open(faq_file, "r", encoding="utf-8") as f:
        FAQS: List[Dict] = json.load(f)
except Exception as e:
    print(f"Error loading {faq_file}: {e}")
    FAQS = []


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)   # remove punctuation
    text = re.sub(r"\s+", " ", text)      # remove extra spaces
    return text


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def keyword_score(user_message: str, keywords: List[str]) -> float:
    msg_words = set(normalize_text(user_message).split())
    score = 0.0

    for kw in keywords:
        kw_words = set(normalize_text(kw).split())

        # exact keyword phrase
        if normalize_text(kw) in normalize_text(user_message):
            score += 2.0
        # partial word overlap
        elif kw_words & msg_words:
            score += 0.7

    return score


def find_special_intent(user_message: str):
    msg = normalize_text(user_message)

    greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"]
    thanks = ["thanks", "thank you", "appreciate"]
    goodbye = ["bye", "goodbye", "see you", "later"]

    for g in greetings:
        if g in msg:
            return {
                "answer": "Hello! I'm your OrthoGuide assistant. How can I help you today? You can ask about braces care, pain, food, cleaning, or treatment.",
                "score": 999
            }

    for t in thanks:
        if t in msg:
            return {
                "answer": "You're welcome! I'm here to help with your orthodontic questions.",
                "score": 999
            }

    for b in goodbye:
        if b in msg:
            return {
                "answer": "You're welcome! If you have more questions about your orthodontic treatment, feel free to ask anytime.",
                "score": 999
            }

    return None


def find_faq_answer(user_message: str, top_n: int = 1) -> List[Dict]:
    if not user_message.strip():
        return [{
            "answer": "Please enter a message.",
            "score": 0
        }]

    # handle greeting / thanks / bye first
    special = find_special_intent(user_message)
    if special:
        return [special]

    results = []

    for faq in FAQS:
        intent = faq.get("intent", "")
        if intent in ["greeting", "thanks", "goodbye", "fallback"]:
            continue

        question = faq.get("question", "")
        keywords = faq.get("keywords", [])

        q_score = similarity(user_message, question) * 3.0
        k_score = keyword_score(user_message, keywords)

        total_score = q_score + k_score

        results.append({
            "intent": intent,
            "answer": faq.get("answer", ""),
            "score": round(total_score, 2)
        })

    results.sort(key=lambda x: x["score"], reverse=True)

    if not results or results[0]["score"] < 1.5:
        return [{
            "answer": "I'm sorry, I didn't understand that. Please ask about braces care, food, pain, cleaning, or orthodontic treatment.",
            "score": 0
        }]

    return results[:top_n]