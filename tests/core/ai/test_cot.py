from src.core.ai.cot import extract_cot


def test_extract_cot_present():
    text = "<thinking>step 1</thinking>Answer"
    clean, reasoning = extract_cot(text)
    assert reasoning == "step 1"
    assert clean == "Answer"


def test_extract_cot_absent():
    text = "Answer only"
    clean, reasoning = extract_cot(text)
    assert reasoning == ""
    assert clean == "Answer only"
