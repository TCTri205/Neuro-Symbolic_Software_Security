import json
import os
from typing import Dict, Optional
from src.core.feedback.schema import FeedbackItem


class FeedbackStore:
    def __init__(self, storage_path: str = ".nsss/feedback.json"):
        # Use absolute path relative to CWD if not absolute
        if not os.path.isabs(storage_path):
            storage_path = os.path.join(os.getcwd(), storage_path)

        self.storage_path = storage_path
        self._ensure_storage()
        self._cache: Dict[str, FeedbackItem] = {}
        self.load()

    def _ensure_storage(self):
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        if not os.path.exists(self.storage_path):
            with open(self.storage_path, "w") as f:
                json.dump({}, f)

    def load(self):
        try:
            with open(self.storage_path, "r") as f:
                content = f.read()
                if not content:
                    self._cache = {}
                    return
                data = json.loads(content)
                self._cache = {k: FeedbackItem(**v) for k, v in data.items()}
        except (json.JSONDecodeError, IOError):
            self._cache = {}

    def save(self):
        with open(self.storage_path, "w") as f:
            data = {k: v.model_dump(mode="json") for k, v in self._cache.items()}
            json.dump(data, f, indent=2)

    def get(self, signature: str) -> Optional[FeedbackItem]:
        return self._cache.get(signature)

    def set(self, item: FeedbackItem):
        self._cache[item.id] = item
        self.save()
