import hashlib
import json
from typing import Any


class CacheKeyGenerator:
    """
    Generates deterministic cache keys for AI requests.
    """

    @staticmethod
    def generate(data: Any) -> str:
        """
        Generates a SHA256 hash for the given data.
        Ensures dictionary keys are sorted to guarantee determinism.
        """
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
