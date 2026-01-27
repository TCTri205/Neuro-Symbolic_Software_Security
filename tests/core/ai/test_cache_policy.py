import time
from src.core.ai.cache_policy import CachePolicyStrategy


def test_cache_policy_no_expiry():
    policy = CachePolicyStrategy(ttl_seconds=None)
    assert policy.is_cache_valid(time.time() - 99999)


def test_cache_policy_expiry():
    policy = CachePolicyStrategy(ttl_seconds=10)
    assert policy.is_cache_valid(time.time() - 5)
    assert not policy.is_cache_valid(time.time() - 20)


def test_cache_policy_force_refresh():
    policy = CachePolicyStrategy(ttl_seconds=10)
    assert policy.should_refresh(time.time(), force_refresh=True)
