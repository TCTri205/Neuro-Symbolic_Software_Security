from typing import Dict, Optional
import logging
from src.core.ai.client import AIClient
from src.core.ai.cache import CacheKeyGenerator
from src.core.ai.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
)

try:
    from src.core.config import settings
except Exception:  # pragma: no cover - config optional for tests
    settings = None


class LLMGatewayService:
    """
    Gateway service for AI interactions.
    Handles caching, rate limiting (delegated to client), and enforcing deterministic parameters.
    """

    def __init__(
        self, client: AIClient, circuit_breaker: Optional[CircuitBreaker] = None
    ):
        self.client = client
        # Simple in-memory cache for now. Ideally should be disk-based or Redis.
        self.cache: Dict[str, str] = {}
        self.circuit_breaker = circuit_breaker or self._resolve_circuit_breaker()

    def analyze(self, system_prompt: str, user_prompt: str) -> str:
        """
        Analyzes the given prompts using the AI client, with caching.
        """
        # Generate deterministic cache key
        payload = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            # We enforce temperature=0 implicitly by caching on inputs.
            # If the client configuration changes (e.g. model), the key should probably include model info.
            # For now, simplistic input hashing.
        }
        cache_key = CacheKeyGenerator.generate(payload)

        if cache_key in self.cache:
            logging.info(f"LLMGateway: Cache hit for key {cache_key[:8]}")
            return self.cache[cache_key]

        logging.info(f"LLMGateway: Cache miss for key {cache_key[:8]}")
        if not self.circuit_breaker.allow_request():
            raise RuntimeError("Circuit breaker open: AI analysis halted")

        try:
            response = self.client.analyze(system_prompt, user_prompt)
        except Exception:
            self.circuit_breaker.record_failure()
            raise
        else:
            self.circuit_breaker.record_success()

        self.cache[cache_key] = response
        return response

    def _resolve_circuit_breaker(self) -> CircuitBreaker:
        config = CircuitBreakerConfig(
            failure_threshold=getattr(settings, "CIRCUIT_BREAKER_FAILURE_THRESHOLD", 3)
            if settings
            else 3,
            recovery_timeout_seconds=getattr(
                settings, "CIRCUIT_BREAKER_RECOVERY_TIMEOUT", 30
            )
            if settings
            else 30.0,
            half_open_success_threshold=getattr(
                settings, "CIRCUIT_BREAKER_HALF_OPEN_SUCCESS_THRESHOLD", 1
            )
            if settings
            else 1,
        )
        return CircuitBreakerRegistry.get_breaker(self._breaker_key(), config)

    def _breaker_key(self) -> str:
        provider = getattr(self.client, "provider", None)
        model = getattr(self.client, "model", None)
        if provider and model:
            return f"{provider}:{model}"
        if provider:
            return provider
        return self.client.__class__.__name__
