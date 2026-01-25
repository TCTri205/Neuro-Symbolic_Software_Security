from abc import ABC, abstractmethod
from typing import Optional
import os
import logging


class AIClient(ABC):
    """Abstract base class for AI connectors."""

    @abstractmethod
    def analyze(self, system_prompt: str, user_prompt: str) -> str:
        """Send a prompt to the AI model and get the response."""
        pass


class MockAIClient(AIClient):
    """Mock client for testing and offline development."""

    def analyze(self, system_prompt: str, user_prompt: str) -> str:
        logging.info("MockAIClient: Received request.")
        return "MOCK_RESPONSE: Analysis complete. No vulnerabilities found (Simulated)."


class OpenAIClient(AIClient):
    """Client for OpenAI-compatible APIs."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        if not self.api_key:
            logging.warning(
                "OpenAIClient initialized without API key. Calls will fail."
            )

    def analyze(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key:
            raise ValueError("OpenAI API Key not configured")

        try:
            # Import here to avoid hard dependency at module level if not used
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key)

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
            )
            return response.choices[0].message.content or ""
        except ImportError:
            raise ImportError(
                "openai package is not installed. Run 'pip install openai'"
            )
        except Exception as e:
            logging.error(f"OpenAI API call failed: {e}")
            raise


class AIClientFactory:
    @staticmethod
    def get_client(provider: str = "mock", **kwargs) -> AIClient:
        if provider == "openai":
            return OpenAIClient(**kwargs)
        return MockAIClient()
