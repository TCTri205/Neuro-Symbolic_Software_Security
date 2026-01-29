from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from threading import Lock
from typing import Dict, Optional

from src.core.ai.cache_policy import CachePolicyStrategy
from src.core.config import settings


@dataclass(frozen=True)
class CacheEntry:
    response: str
    updated_at: float


class LLMCacheStore:
    _instance: Optional["LLMCacheStore"] = None
    _lock: Lock = Lock()

    def __init__(
        self,
        storage_path: Optional[str] = None,
        policy: Optional[CachePolicyStrategy] = None,
    ) -> None:
        path = storage_path or getattr(
            settings, "LLM_CACHE_PATH", ".nsss/cache/llm_cache.json"
        )
        if not os.path.isabs(path):
            path = os.path.join(os.getcwd(), path)
        self.storage_path = path
        self._policy = policy or CachePolicyStrategy()
        self._cache: Dict[str, CacheEntry] = {}
        self._fs_lock = Lock()
        self._ensure_storage()
        self._load()

    @classmethod
    def get_instance(cls) -> "LLMCacheStore":
        with cls._lock:
            if cls._instance is None:
                cls._instance = LLMCacheStore()
            return cls._instance

    def get(self, key: str) -> Optional[str]:
        entry = self._cache.get(key)
        if not entry:
            return None
        if not self._policy.is_cache_valid(entry.updated_at):
            self._cache.pop(key, None)
            self._persist()
            return None
        return entry.response

    def set(self, key: str, response: str) -> None:
        self._cache[key] = CacheEntry(response=response, updated_at=time.time())
        self._persist()

    def clear(self) -> None:
        self._cache = {}
        self._persist()

    def _ensure_storage(self) -> None:
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        if not os.path.exists(self.storage_path):
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def _load(self) -> None:
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                content = f.read()
            if not content:
                self._cache = {}
                return
            raw = json.loads(content)
            self._cache = {
                k: CacheEntry(response=v["response"], updated_at=v["updated_at"])
                for k, v in raw.items()
            }
        except (json.JSONDecodeError, OSError, KeyError, TypeError):
            self._cache = {}

    def _persist(self) -> None:
        with self._fs_lock:
            data = {
                k: {"response": v.response, "updated_at": v.updated_at}
                for k, v in self._cache.items()
            }
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
