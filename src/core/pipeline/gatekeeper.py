from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Sequence
import os
import time

from src.core.telemetry import get_logger


@dataclass
class BudgetConfiguration:
    max_tokens_per_scan: Optional[int] = 100000
    max_cost_per_scan: Optional[float] = None
    max_completion_tokens: int = 1024
    cost_per_1k_tokens: Dict[str, float] = field(
        default_factory=lambda: {
            "gemini": 0.0,
            "google": 0.0,
            "openai": 0.0,
        }
    )
    rate_limit_cooldown_seconds: int = 60


@dataclass
class GateDecision:
    allowed: bool
    reason: str
    estimated_tokens: int = 0
    estimated_cost: float = 0.0


class GatekeeperService:
    def __init__(self, config: Optional[BudgetConfiguration] = None) -> None:
        self.config = config or BudgetConfiguration()
        self.logger = get_logger(__name__)
        self.tokens_used = 0
        self.cost_used = 0.0
        self.rate_limit_until: Dict[str, float] = {}

    def reset_scan(self) -> None:
        self.tokens_used = 0
        self.cost_used = 0.0

    def preferred_provider(self) -> str:
        if self._has_gemini_key():
            return "gemini"
        return os.getenv("LLM_PROVIDER", "openai").lower()

    def evaluate(self, prompt: Any, client: Any) -> GateDecision:
        if not getattr(client, "is_configured", False):
            return GateDecision(False, "Provider not configured")

        provider = getattr(client, "provider", "openai")
        if self.is_rate_limited(provider):
            return GateDecision(False, "Provider rate limit cooldown active")

        estimated_prompt_tokens = self._estimate_tokens(prompt)
        estimated_total_tokens = (
            estimated_prompt_tokens + self.config.max_completion_tokens
        )

        if self.config.max_tokens_per_scan is not None:
            projected_tokens = self.tokens_used + estimated_total_tokens
            if projected_tokens > self.config.max_tokens_per_scan:
                return GateDecision(False, "Token budget exceeded")

        estimated_cost = self._estimate_cost(
            provider, getattr(client, "model", ""), estimated_total_tokens
        )
        if self.config.max_cost_per_scan is not None:
            projected_cost = self.cost_used + estimated_cost
            if projected_cost > self.config.max_cost_per_scan:
                return GateDecision(False, "Cost budget exceeded")

        self.tokens_used += estimated_total_tokens
        self.cost_used += estimated_cost

        return GateDecision(
            True,
            "Allowed",
            estimated_tokens=estimated_total_tokens,
            estimated_cost=estimated_cost,
        )

    def record_response(
        self,
        client: Any,
        response: Optional[Dict[str, Any]],
        decision: GateDecision,
    ) -> None:
        if not response:
            return

        provider = getattr(client, "provider", "openai")
        status = response.get("status")
        if status == 429:
            self.record_rate_limit(provider)

        usage = self._extract_usage(response)
        if not usage:
            return

        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        actual_total = prompt_tokens + completion_tokens
        delta_tokens = actual_total - decision.estimated_tokens
        self.tokens_used = max(0, self.tokens_used + delta_tokens)

        actual_cost = self._estimate_cost(
            provider, getattr(client, "model", ""), actual_total
        )
        delta_cost = actual_cost - decision.estimated_cost
        self.cost_used = max(0.0, self.cost_used + delta_cost)

    def record_rate_limit(
        self, provider: str, retry_after_seconds: Optional[int] = None
    ) -> None:
        cooldown = retry_after_seconds or self.config.rate_limit_cooldown_seconds
        self.rate_limit_until[provider] = time.time() + cooldown

    def is_rate_limited(self, provider: str) -> bool:
        until = self.rate_limit_until.get(provider, 0.0)
        return time.time() < until

    def _estimate_tokens(self, prompt: Any) -> int:
        text = self._flatten_prompt(prompt)
        if not text:
            return 0
        return max(1, len(text) // 4)

    def _flatten_prompt(self, prompt: Any) -> str:
        if isinstance(prompt, str):
            return prompt
        if isinstance(prompt, Sequence):
            chunks = []
            for item in prompt:
                if isinstance(item, dict):
                    chunks.append(item.get("content", ""))
                else:
                    chunks.append(str(item))
            return " ".join(chunks)
        return str(prompt)

    def _estimate_cost(self, provider: str, model: str, tokens: int) -> float:
        if tokens <= 0:
            return 0.0
        cost_per_1k = self.config.cost_per_1k_tokens.get(provider, 0.0)
        return (tokens / 1000.0) * cost_per_1k

    def _extract_usage(self, response: Dict[str, Any]) -> Optional[Dict[str, int]]:
        raw = response.get("raw", {})
        if isinstance(raw, dict) and "usage" in raw:
            usage = raw.get("usage", {})
            return {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
            }
        if isinstance(raw, dict) and "usageMetadata" in raw:
            usage = raw.get("usageMetadata", {})
            return {
                "prompt_tokens": usage.get("promptTokenCount", 0),
                "completion_tokens": usage.get("candidatesTokenCount", 0),
            }
        return None

    def _has_gemini_key(self) -> bool:
        if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
            return True
        for i in [2, 3]:
            if os.getenv(f"GEMINI_API_KEY_{i}"):
                return True
        try:
            from src.core.config import settings

            if getattr(settings, "GEMINI_API_KEY", None):
                return True
            for i in [2, 3]:
                if getattr(settings, f"GEMINI_API_KEY_{i}", None):
                    return True
        except Exception:
            return False
        return False
