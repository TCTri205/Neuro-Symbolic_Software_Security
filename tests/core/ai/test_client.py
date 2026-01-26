import pytest

from src.core.ai.client import AIClientFactory, MockAIClient, LLMClient
from src.core.config import settings


class TestAIClient:
    def test_factory_mock(self):
        client = AIClientFactory.get_client("mock")
        assert isinstance(client, MockAIClient)
        response = client.analyze("sys", "user")
        assert "MOCK_RESPONSE" in response

    def test_factory_openai(self):
        client = AIClientFactory.get_client("openai", api_key="fake-key")
        assert isinstance(client, LLMClient)
        assert client.api_key == "fake-key"

    def test_openai_missing_key_behavior(self, monkeypatch):
        # Ensure it doesn't crash on init without key (lazy check or warning)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY_2", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY_3", raising=False)
        monkeypatch.setattr(settings, "OPENAI_API_KEY", None, raising=False)
        monkeypatch.setattr(settings, "OPENAI_API_KEY_2", None, raising=False)
        monkeypatch.setattr(settings, "OPENAI_API_KEY_3", None, raising=False)

        client = LLMClient(provider="openai", api_key=None)
        # But should crash on call
        with pytest.raises(ValueError):
            client.analyze("sys", "user")
