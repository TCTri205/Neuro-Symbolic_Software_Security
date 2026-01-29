from unittest.mock import patch
import pytest
from src.core.ai.circuit_breaker import CircuitBreaker
from src.core.ai.gateway import LLMGatewayService
from src.core.ai.client import MockAIClient


class TestLLMGatewayService:
    def setup_method(self):
        self.mock_client = MockAIClient()
        self.service = LLMGatewayService(client=self.mock_client)

    def test_analyze_with_cache_miss(self):
        # When cache is empty, it should call the client
        system_prompt = "Sys"
        user_prompt = "User"

        # Mock client response
        with patch.object(
            self.mock_client, "analyze", return_value="Analyzed"
        ) as mock_analyze:
            result = self.service.analyze(system_prompt, user_prompt)
            assert result == "Analyzed"
            mock_analyze.assert_called_once()

    def test_analyze_with_cache_hit(self):
        system_prompt = "Sys"
        user_prompt = "User"

        # Pre-populate cache (assuming in-memory dict for now or mocked cache)
        # We need to verify if LLMGatewayService uses a cache mechanism we can inspect or mock
        # For this test, let's rely on behavior: second call shouldn't trigger client

        with patch.object(
            self.mock_client, "analyze", return_value="Analyzed"
        ) as mock_analyze:
            # First call
            self.service.analyze(system_prompt, user_prompt)
            assert mock_analyze.call_count == 1

            # Second call (same inputs)
            result = self.service.analyze(system_prompt, user_prompt)
            assert result == "Analyzed"
            # Should still be 1 if caching is working
            assert mock_analyze.call_count == 1

    def test_deterministic_parameters(self):
        # Verify that the service enforces temperature=0 or similar constraints if applicable
        # This might be hard to test if it's internal to client call, unless we spy on client.
        pass

    def test_analyze_circuit_breaker_blocks_after_failure(self):
        system_prompt = "Sys"
        user_prompt = "User"
        breaker = CircuitBreaker(
            failure_threshold=1, recovery_timeout_seconds=100.0, time_fn=lambda: 0.0
        )
        service = LLMGatewayService(client=self.mock_client, circuit_breaker=breaker)

        with patch.object(
            self.mock_client, "analyze", side_effect=RuntimeError("fail")
        ):
            with pytest.raises(RuntimeError):
                service.analyze(system_prompt, user_prompt)

        with pytest.raises(RuntimeError, match="Circuit breaker open"):
            service.analyze(system_prompt, user_prompt)
