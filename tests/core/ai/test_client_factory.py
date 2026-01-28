import os
import unittest
from unittest.mock import patch, MagicMock

from src.core.ai.client import AIClientFactory, MockAIClient, LLMClient

# We can't easily import LocalLLMClient if unsloth is missing, but we can mock the import or check for it
try:
    from src.core.ai.local_client import LocalLLMClient
except ImportError:
    LocalLLMClient = None


class TestAIClientFactory(unittest.TestCase):
    def test_get_mock_client(self):
        client = AIClientFactory.get_client("mock")
        self.assertIsInstance(client, MockAIClient)

    def test_get_openai_client(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}):
            client = AIClientFactory.get_client("openai")
            self.assertIsInstance(client, LLMClient)
            self.assertEqual(client.provider, "openai")

    def test_get_gemini_client(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test"}):
            client = AIClientFactory.get_client("gemini")
            self.assertIsInstance(client, LLMClient)
            self.assertEqual(client.provider, "gemini")

    @patch("src.core.ai.local_client.LocalLLMClient")
    def test_get_local_client(self, MockLocalLLMClient):
        # We mock the class itself so we don't need unsloth installed
        client = AIClientFactory.get_client("local")
        self.assertTrue(MockLocalLLMClient.called)

    def test_default_client(self):
        client = AIClientFactory.get_client("unknown_provider")
        self.assertIsInstance(client, MockAIClient)


if __name__ == "__main__":
    unittest.main()
