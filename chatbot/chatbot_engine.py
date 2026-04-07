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
    msg = normalize_text(user_message)
    msg_words = set(msg.split())
    score = 0.0

    for kw in keywords:
        kw_norm = normalize_text(kw)
        kw_words = set(kw_norm.split())

        # full phrase match
        if kw_norm and kw_norm in msg:
            score += 2.0
        # partial word overlap
        elif kw_words and (kw_words & msg_words):
            score += 0.7

    return score


def find_special_intent(user_message: str):
    msg = normalize_text(user_message)

    greeting_patterns = [
        "hi",
        "hello",
        "hey",
        "good morning",
        "good afternoon",
        "good evening"
    ]

    thanks_patterns = [
        "thanks",
        "thank you",
        "appreciate"
    ]

    goodbye_patterns = [
        "bye",
        "goodbye",
        "see you",
        "see you later"
    ]

    # greeting should return greeting answer, not fallback
    for g in greeting_patterns:
        if g == msg or msg.startswith(g + " ") or (" " + g + " ") in (" " + msg + " "):
            return {
                "intent": "greeting",
                "answer": "Hello! I'm your OrthoGuide assistant. How can I help you today? You can ask about braces care, pain, food, cleaning, or treatment.",
                "score": 999
            }

    for t in thanks_patterns:
        if t == msg or t in msg:
            return {
                "intent": "thanks",
                "answer": "You're welcome! I'm here to help with your orthodontic questions.",
                "score": 999
            }

    for b in goodbye_patterns:
        if b == msg or b in msg:
            return {
                "intent": "goodbye",
                "answer": "You're welcome! If you have more questions about your orthodontic treatment, feel free to ask anytime.",
                "score": 999
            }

    return None


def find_faq_answer(user_message: str, top_n: int = 1) -> List[Dict]:
    if not user_message.strip():
        return [{
            "intent": "empty",
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
            "question": question,
            "answer": faq.get("answer", ""),
            "score": round(total_score, 2)
        })

    results.sort(key=lambda x: x["score"], reverse=True)

    # debug
    if results:
        print(f"USER: {user_message}")
        print(f"BEST MATCH: {results[0]['intent']}")
        print(f"SCORE: {results[0]['score']}")
        print("-" * 50)

    if not results or results[0]["score"] < 1.5:
        return [{
            "intent": "fallback",
            "answer": "I'm sorry, I didn't understand that. Please ask about braces care, food, pain, cleaning, or orthodontic treatment.",
            "score": 0
        }]

    return results[:top_n]