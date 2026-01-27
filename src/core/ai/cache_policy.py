from dataclasses import dataclass
import time


@dataclass
class CachePolicyStrategy:
    """
    Defines cache invalidation rules for deterministic reuse.
    If ttl_seconds is None, cache never expires.
    """

    ttl_seconds: int | None = None

    def is_cache_valid(self, last_updated: float) -> bool:
        if self.ttl_seconds is None:
            return True
        return (time.time() - last_updated) <= self.ttl_seconds

    def should_refresh(self, last_updated: float, force_refresh: bool = False) -> bool:
        if force_refresh:
            return True
        return not self.is_cache_valid(last_updated)
