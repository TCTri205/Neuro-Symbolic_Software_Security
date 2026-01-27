from typing import Dict
import logging
from src.core.ai.client import AIClient
from src.core.ai.cache import CacheKeyGenerator


class LLMGatewayService:
    """
    Gateway service for AI interactions.
    Handles caching, rate limiting (delegated to client), and enforcing deterministic parameters.
    """

    def __init__(self, client: AIClient):
        self.client = client
        # Simple in-memory cache for now. Ideally should be disk-based or Redis.
        self.cache: Dict[str, str] = {}

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
        response = self.client.analyze(system_prompt, user_prompt)

        self.cache[cache_key] = response
        return response
