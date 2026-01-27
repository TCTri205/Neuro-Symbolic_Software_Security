import re
from typing import Tuple


THINKING_PATTERN = re.compile(r"<thinking>(.*?)</thinking>", re.DOTALL | re.IGNORECASE)


def extract_cot(text: str) -> Tuple[str, str]:
    """
    Extracts chain-of-thought content from <thinking> tags.
    Returns (clean_text, reasoning_trace).
    """
    match = THINKING_PATTERN.search(text)
    if not match:
        return text, ""

    reasoning = match.group(1).strip()
    clean_text = THINKING_PATTERN.sub("", text).strip()
    return clean_text, reasoning
