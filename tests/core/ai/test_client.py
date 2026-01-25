import pytest
from src.core.ai.client import AIClientFactory, MockAIClient, OpenAIClient


class TestAIClient:
    def test_factory_mock(self):
        client = AIClientFactory.get_client("mock")
        assert isinstance(client, MockAIClient)
        response = client.analyze("sys", "user")
        assert "MOCK_RESPONSE" in response

    def test_factory_openai(self):
        client = AIClientFactory.get_client("openai", api_key="fake-key")
        assert isinstance(client, OpenAIClient)
        assert client.api_key == "fake-key"

    def test_openai_missing_key_behavior(self):
        # Ensure it doesn't crash on init without key (lazy check or warning)
        client = OpenAIClient(api_key=None)
        # But should crash on call
        with pytest.raises(ValueError):
            client.analyze("sys", "user")
