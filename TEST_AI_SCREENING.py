from ai_assistant import analyze_symptoms

def test_empty():
    try: analyze_symptoms("")
    except ValueError: return
    raise AssertionError("Empty symptoms should be rejected")

def test_common_symptoms():
    r=analyze_symptoms("fever, cough and sore throat")
    assert r["category"] != "Unclassified symptoms"
    assert r["risk"] in ("Low", "Medium", "High")

def test_emergency_phrase():
    r=analyze_symptoms("chest pain")
    assert r["risk"] == "High" and r["urgent"] is True

if __name__ == "__main__":
    test_empty(); test_common_symptoms(); test_emergency_phrase()
    print("AI screening rules passed.")
