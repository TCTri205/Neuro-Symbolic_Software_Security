import json
from src.core.ai.cache import CacheKeyGenerator


def test_cache_key_deterministic_dict():
    data1 = {"a": 1, "b": 2, "c": [1, 2, 3]}
    data2 = {"c": [1, 2, 3], "b": 2, "a": 1}

    key1 = CacheKeyGenerator.generate(data1)
    key2 = CacheKeyGenerator.generate(data2)

    assert key1 == key2
    assert len(key1) == 64  # SHA256 hex digest length


def test_cache_key_nested():
    data1 = {"context": {"line": 10, "file": "foo.py"}, "code": "print(1)"}
    data2 = {"code": "print(1)", "context": {"file": "foo.py", "line": 10}}

    assert CacheKeyGenerator.generate(data1) == CacheKeyGenerator.generate(data2)


def test_cache_key_list_order_matters():
    data1 = {"list": [1, 2]}
    data2 = {"list": [2, 1]}

    assert CacheKeyGenerator.generate(data1) != CacheKeyGenerator.generate(data2)


def test_cache_key_types():
    # Helper to test non-dict types if needed, though mostly we hash dict payloads
    assert CacheKeyGenerator.generate("string") == CacheKeyGenerator.generate("string")
    assert CacheKeyGenerator.generate(123) == CacheKeyGenerator.generate(123)
