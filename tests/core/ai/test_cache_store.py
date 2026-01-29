import json

from src.core.ai.cache_policy import CachePolicyStrategy
from src.core.ai.cache_store import LLMCacheStore


def test_cache_store_persists(tmp_path):
    cache_path = tmp_path / "llm_cache.json"
    store = LLMCacheStore(storage_path=str(cache_path))
    store.set("key", "value")

    reloaded = LLMCacheStore(storage_path=str(cache_path))
    assert reloaded.get("key") == "value"


def test_cache_store_expires(tmp_path, monkeypatch):
    cache_path = tmp_path / "llm_cache.json"
    policy = CachePolicyStrategy(ttl_seconds=1)
    store = LLMCacheStore(storage_path=str(cache_path), policy=policy)
    store.set("key", "value")

    with open(cache_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    updated_at = data["key"]["updated_at"]

    monkeypatch.setattr("src.core.ai.cache_store.time.time", lambda: updated_at + 100)
    assert store.get("key") is None
