"""Transparent, rule-based symptom screening for the Suraksha Health Care demo.

This module is educational decision support, not a diagnostic system.
"""
import re

# Phrase groups are deliberately simple and inspectable. They are not a substitute
# for a clinician or a medically validated triage protocol.
EMERGENCY_GROUPS = {
    "Possible breathing emergency": ["difficulty breathing", "trouble breathing", "shortness of breath", "breathing difficulty", "cannot breathe", "can't breathe", "breathlessness", "severe breathing"],
    "Possible chest-pain emergency": ["chest pain", "chest pressure", "pressure in chest", "pain in chest"],
    "Possible loss of consciousness": ["unconscious", "passed out", "loss of consciousness", "not responding"],
    "Possible severe bleeding": ["heavy bleeding", "severe bleeding", "bleeding heavily"],
    "Possible stroke warning sign": ["face drooping", "slurred speech", "sudden weakness", "sudden numbness"],
    "Possible severe allergic reaction": ["throat swelling", "swollen tongue", "anaphylaxis"],
}
GROUPS = {
    "Respiratory / flu-like": ["fever", "cough", "cold", "sore throat", "throat pain", "runny nose", "congestion", "chills", "body ache", "body aches", "tiredness", "fatigue"],
    "Digestive": ["stomach pain", "abdominal pain", "vomiting", "diarrhea", "diarrhoea", "nausea", "constipation", "indigestion"],
    "Pain / inflammation": ["headache", "migraine", "joint pain", "back pain", "swelling", "rash", "pain"],
    "Neurological / general": ["dizziness", "dizzy", "blurred vision", "weakness", "numbness", "confusion"],
}


def _normalise(value):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]", " ", str(value or "").lower())).strip()


def analyze_symptoms(symptoms):
    """Return a transparent demo screening result from free-text symptoms."""
    text = _normalise(symptoms)
    if not text:
        raise ValueError("Please enter at least one symptom.")

    emergency_matches = [label for label, phrases in EMERGENCY_GROUPS.items()
                         if any(_normalise(phrase) in text for phrase in phrases)]
    matched = []
    categories = []
    for category, phrases in GROUPS.items():
        hits = [phrase for phrase in phrases if _normalise(phrase) in text]
        if hits:
            categories.append(category)
            matched.extend(hits)

    if emergency_matches:
        return {
            "risk": "High", "category": "Urgent warning signs",
            "recommendation": "These symptoms may indicate an emergency. Contact local emergency services or seek immediate medical attention now. Do not rely on this screening tool.",
            "factors": emergency_matches + (matched[:4]), "risk_score": 90,
            "explanation": "One or more phrases matched the application's emergency-warning list.",
            "urgent": True,
        }

    if len(set(matched)) >= 3 or ("Respiratory / flu-like" in categories and len(set(matched)) >= 2):
        risk, score = "Medium", 55
    elif matched:
        risk, score = "Medium", 40
    else:
        risk, score = "Low", 15

    category = ", ".join(categories) if categories else "Unclassified symptoms"
    if risk == "Medium":
        recommendation = "Consider contacting a qualified healthcare professional, especially if symptoms are worsening, persistent, or concerning."
    else:
        recommendation = "No listed warning pattern was detected by these simple rules. Monitor symptoms and seek professional advice if concerned or symptoms persist."
    return {
        "risk": risk, "category": category, "recommendation": recommendation,
        "factors": sorted(set(matched)), "risk_score": score,
        "explanation": "This category is based on the symptom phrases matched by transparent demo rules.",
        "urgent": False,
    }
