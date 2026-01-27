import os
import time
from typing import Optional
import requests
from src.core.ai.client import AIClient


class RemoteAIClient(AIClient):
    """Client for centralized GPU server mode."""

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = base_url or os.getenv(
            "NSSS_SERVER_URL", "http://localhost:8000"
        )
        self.api_key = api_key or os.getenv("NSSS_API_KEY")

    def analyze(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "function_signature": user_prompt,
            "language": "python",
            "vulnerability_type": "unknown",
            "context": {},
            "privacy_mask": {"enabled": False, "map": {}},
            "metadata": {
                "mode": "precision",
                "request_id": str(int(time.time() * 1000)),
            },
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        response = requests.post(
            f"{self.base_url}/analyze", json=payload, headers=headers, timeout=30
        )
        response.raise_for_status()
        body = response.json()
        if body.get("status") != "success":
            raise RuntimeError(body.get("message", "Remote server error"))
        data = body.get("data", {})
        return data.get("analysis_summary", "")
