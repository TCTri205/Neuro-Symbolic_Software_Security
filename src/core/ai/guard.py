from typing import Iterable


class AntiHallucinationGuard:
    """
    Guards against hallucinated instructions like installing or importing new libs.
    """

    def __init__(self, banned_tokens: Iterable[str] | None = None):
        self.banned_tokens = [
            token.lower()
            for token in (
                banned_tokens or ["import ", "pip install", "apt-get", "brew install"]
            )
        ]

    def validate(self, text: str) -> None:
        lowered = text.lower()
        for token in self.banned_tokens:
            if token in lowered:
                raise ValueError(f"Hallucination guard triggered: '{token.strip()}'")
