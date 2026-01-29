from unittest.mock import patch

import pytest

from src.core.ai.cache_store import LLMCacheStore
from src.core.ai.circuit_breaker import CircuitBreaker
from src.core.ai.gateway import LLMGatewayService
from src.core.ai.client import MockAIClient


def _build_service(tmp_path):
    cache_store = LLMCacheStore(storage_path=str(tmp_path / "llm_cache.json"))
    client = MockAIClient()
    service = LLMGatewayService(client=client, cache_store=cache_store)
    return client, service


class TestLLMGatewayService:
    def test_analyze_with_cache_miss(self, tmp_path):
        # When cache is empty, it should call the client
        mock_client, service = _build_service(tmp_path)
        system_prompt = "Sys"
        user_prompt = "User"

        # Mock client response
        with patch.object(
            mock_client, "analyze", return_value="Analyzed"
        ) as mock_analyze:
            result = service.analyze(system_prompt, user_prompt)
            assert result == "Analyzed"
            mock_analyze.assert_called_once()

    def test_analyze_with_cache_hit(self, tmp_path):
        mock_client, service = _build_service(tmp_path)
        system_prompt = "Sys"
        user_prompt = "User"

        # Pre-populate cache (assuming in-memory dict for now or mocked cache)
        # We need to verify if LLMGatewayService uses a cache mechanism we can inspect or mock
        # For this test, let's rely on behavior: second call shouldn't trigger client

        with patch.object(
            mock_client, "analyze", return_value="Analyzed"
        ) as mock_analyze:
            # First call
            service.analyze(system_prompt, user_prompt)
            assert mock_analyze.call_count == 1

            # Second call (same inputs)
            result = service.analyze(system_prompt, user_prompt)
            assert result == "Analyzed"
            # Should still be 1 if caching is working
            assert mock_analyze.call_count == 1

    def test_deterministic_parameters(self):
        # Verify that the service enforces temperature=0 or similar constraints if applicable
        # This might be hard to test if it's internal to client call, unless we spy on client.
        pass

    def test_analyze_circuit_breaker_blocks_after_failure(self, tmp_path):
        mock_client, _ = _build_service(tmp_path)
        system_prompt = "Sys"
        user_prompt = "User"
        breaker = CircuitBreaker(
            failure_threshold=1, recovery_timeout_seconds=100.0, time_fn=lambda: 0.0
        )
        cache_store = LLMCacheStore(storage_path=str(tmp_path / "llm_cache.json"))
        service = LLMGatewayService(
            client=mock_client, circuit_breaker=breaker, cache_store=cache_store
        )

        with patch.object(mock_client, "analyze", side_effect=RuntimeError("fail")):
            with pytest.raises(RuntimeError):
                service.analyze(system_prompt, user_prompt)

        with pytest.raises(RuntimeError, match="Circuit breaker open"):
            service.analyze(system_prompt, user_prompt)

    def test_cache_persists_across_instances(self, tmp_path):
        cache_path = tmp_path / "llm_cache.json"
        client_one = MockAIClient()
        client_two = MockAIClient()

        store_one = LLMCacheStore(storage_path=str(cache_path))
        service_one = LLMGatewayService(client=client_one, cache_store=store_one)

        with patch.object(client_one, "analyze", return_value="Analyzed") as mock_one:
            service_one.analyze("Sys", "User")
            mock_one.assert_called_once()

        store_two = LLMCacheStore(storage_path=str(cache_path))
        service_two = LLMGatewayService(client=client_two, cache_store=store_two)

        with patch.object(client_two, "analyze") as mock_two:
            assert service_two.analyze("Sys", "User") == "Analyzed"
            mock_two.assert_not_called()
