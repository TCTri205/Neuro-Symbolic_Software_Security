from typing import List, Optional
import logging
from src.core.ai.client import LLMClient


class FallbackPolicy:
    """
    Manages fallback logic for AI clients.
    Supports a chain of providers.
    """

    def __init__(self, primary_provider: str, fallback_providers: List[str]):
        self.providers = [primary_provider] + fallback_providers
        self.current_index = 0

    def get_current_provider(self) -> str:
        if self.current_index < len(self.providers):
            return self.providers[self.current_index]
        return self.providers[-1]  # Stay on last one? Or None?

    def should_fallback(self, error: Exception) -> bool:
        # Determine if error is transient or fatal
        # For now, fallback on everything except maybe invalid request
        return True

    def next_provider(self) -> Optional[str]:
        if self.current_index + 1 < len(self.providers):
            self.current_index += 1
            logging.warning(
                f"FallbackPolicy: Switching to provider {self.providers[self.current_index]}"
            )
            return self.providers[self.current_index]
        return None

    def reset(self):
        self.current_index = 0
