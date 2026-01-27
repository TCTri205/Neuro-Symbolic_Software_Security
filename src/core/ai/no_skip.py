from dataclasses import dataclass


@dataclass
class NoSkipPolicy:
    """
    Ensures long contexts are summarized instead of skipped.
    Uses a simple head/tail strategy to keep key signals.
    """

    max_chars: int = 4000
    head_ratio: float = 0.6

    def apply(self, text: str) -> str:
        if len(text) <= self.max_chars:
            return text

        head_len = int(self.max_chars * self.head_ratio)
        tail_len = self.max_chars - head_len
        head = text[:head_len].rstrip()
        tail = text[-tail_len:].lstrip()

        return f"{head}\n...<truncated>...\n{tail}"
