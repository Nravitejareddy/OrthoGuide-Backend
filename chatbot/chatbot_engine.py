import json
import os
from difflib import SequenceMatcher
from typing import List, Dict, Tuple

# Load FAQs once
faq_file = os.path.join(os.path.dirname(__file__), "orthodontic_faqs.json")
try:
    with open(faq_file, "r", encoding="utf-8") as f:
        FAQS: List[Dict] = json.load(f)
except Exception as e:
    print(f"Error loading {faq_file}: {e}")
    FAQS = []

def similarity(a: str, b: str) -> float:
    """Return a score between 0 and 1 indicating string similarity"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def score_faqs(user_message: str) -> List[Tuple[Dict, float]]:
    """
    Score each FAQ based on keyword match + question similarity.
    Returns a list of tuples: (faq, score) sorted by score descending.
    """
    results = []
    msg = user_message.lower()

    for faq in FAQS:
        score = 0.0

        # Keyword boost
        keywords = faq.get("keywords", [])
        for kw in keywords:
            if kw.lower() in msg:
                score += 0.5  # weight for keyword match

        # Question similarity
        question = faq.get("question", "")
        sim_score = similarity(user_message, question)
        score += sim_score  # add similarity score

        if score > 0:
            results.append((faq, score))

    # Sort by score descending
    results.sort(key=lambda x: x[1], reverse=True)
    return results

def find_faq_answer(user_message: str, top_n: int = 1) -> List[Dict]:
    """
    Returns the top N FAQ answers with their scores
    """
    scored = score_faqs(user_message)
    if not scored:
        return [{"answer": "Sorry, I could not find an answer. Please contact your clinician.", "score": 0}]

    top_results = []
    for faq, score in scored[:top_n]:
        top_results.append({
            "answer": faq.get("answer", ""),
            "score": round(score, 2)
        })
    return top_results