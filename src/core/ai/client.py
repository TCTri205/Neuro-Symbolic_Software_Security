from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
import os
import json
import logging
import urllib.request
import urllib.error

from src.core.telemetry.metrics import MetricsCollector, MeasureLatency


class AIClient(ABC):
    """Abstract base class for AI connectors."""

    @abstractmethod
    def analyze(self, system_prompt: str, user_prompt: str) -> str:
        """Send a prompt to the AI model and get the response."""
        pass


class MockAIClient(AIClient):
    """Mock client for testing and offline development."""

    def analyze(self, system_prompt: str, user_prompt: str) -> str:
        with MeasureLatency("ai_inference_mock"):
            logging.info("MockAIClient: Received request.")
            return "MOCK_RESPONSE: Analysis complete. No vulnerabilities found (Simulated)."


class LLMClient(AIClient):
    """
    Robust AI client supporting multiple providers (OpenAI, Gemini),
    key rotation, fallback strategies, and telemetry.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 30,
        base_url: Optional[str] = None,
        enable_rotation: bool = True,
        enable_fallback: bool = True,
    ):
        settings = self._load_settings()

        # Provider resolution
        env_provider = os.getenv("LLM_PROVIDER")
        settings_provider = (
            getattr(settings, "LLM_PROVIDER", None) if settings else None
        )
        self.provider = (
            provider or env_provider or settings_provider or "openai"
        ).lower()

        # Fallback provider resolution
        env_fallback = os.getenv("LLM_FALLBACK_PROVIDER")
        settings_fallback = (
            getattr(settings, "LLM_FALLBACK_PROVIDER", None) if settings else None
        )
        self.fallback_provider = (env_fallback or settings_fallback or "").lower()

        # Model resolution
        env_model = os.getenv("LLM_MODEL")
        settings_model = getattr(settings, "LLM_MODEL", None) if settings else None
        self.model = (
            model or env_model or settings_model or self._default_model(self.provider)
        )

        self.settings = settings
        self.enable_rotation = enable_rotation
        self.enable_fallback = enable_fallback and bool(self.fallback_provider)

        # Resolve all API keys for rotation
        self.api_keys = (
            self._resolve_all_api_keys(self.provider, settings)
            if not api_key
            else [api_key]
        )
        self.api_key = self.api_keys[0] if self.api_keys else None
        self.current_key_index = 0

        self.timeout = timeout

        # Base URL resolution
        env_openai_base = os.getenv("OPENAI_BASE_URL")
        env_gemini_base = os.getenv("GEMINI_BASE_URL")
        settings_openai_base = (
            getattr(settings, "OPENAI_BASE_URL", None) if settings else None
        )
        settings_gemini_base = (
            getattr(settings, "GEMINI_BASE_URL", None) if settings else None
        )

        self.base_url = base_url or self._default_base_url(
            self.provider,
            env_openai_base=env_openai_base,
            env_gemini_base=env_gemini_base,
            settings_openai_base=settings_openai_base,
            settings_gemini_base=settings_gemini_base,
        )

        self.metrics = MetricsCollector()

        if not self.api_key:
            logging.warning(
                f"LLMClient initialized without API key for provider {self.provider}."
            )

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def analyze(self, system_prompt: str, user_prompt: str) -> str:
        """Main entry point for analysis."""
        if not self.api_key:
            # If no key, fail fast or return error string?
            # Keep fail-fast behavior when no API key is configured.
            raise ValueError(f"No API Key configured for {self.provider}")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        with MeasureLatency(f"ai_inference_{self.provider}"):
            response = self.chat(messages)

        if response.get("error"):
            logging.error(
                f"AI Analysis failed: {response.get('error')} - {response.get('reason')}"
            )
            raise RuntimeError(f"AI Analysis failed: {response.get('error')}")

        return response.get("content", "")

    def chat(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Internal chat method with rotation and fallback."""

        # Try primary provider with key rotation
        result = self._chat_with_rotation(messages, self.provider)

        # If failed and fallback is enabled, try fallback provider
        if result.get("error") and self.enable_fallback:
            logging.warning(
                f"Primary provider {self.provider} failed. Attempting fallback to {self.fallback_provider}."
            )
            fallback_result = self._try_fallback(messages)
            if fallback_result and not fallback_result.get("error"):
                return fallback_result

        return result

    def _chat_with_rotation(
        self, messages: List[Dict[str, str]], provider: str
    ) -> Dict[str, Any]:
        """Try chat with key rotation if enabled"""
        if not self.api_keys:
            return {"error": "no api keys configured"}

        attempts = len(self.api_keys) if self.enable_rotation else 1
        result: Dict[str, Any] = {"error": "uninitialized"}

        for attempt in range(attempts):
            if not self.api_key:
                continue

            result = self._execute_chat(messages, provider, self.api_key)

            should_rotate = self._should_rotate_key(result)

            if not should_rotate:
                # Success or non-retriable error
                return result

            if attempt < attempts - 1:
                # Rotate to next key
                logging.info(
                    f"Rotating API key for {provider} due to rate limit/quota."
                )
                self.current_key_index = (self.current_key_index + 1) % len(
                    self.api_keys
                )
                self.api_key = self.api_keys[self.current_key_index]

        return result

    def _try_fallback(self, messages: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
        """Try fallback provider if primary fails"""
        fallback_keys = self._resolve_all_api_keys(
            self.fallback_provider, self.settings
        )
        if not fallback_keys:
            return None

        original_provider = self.provider
        original_key = self.api_key
        original_model = self.model
        original_base_url = self.base_url

        try:
            self.provider = self.fallback_provider
            self.api_key = fallback_keys[0]
            self.model = self._default_model(self.fallback_provider)
            self.base_url = self._default_base_url(self.fallback_provider)

            fallback_key = self.api_key or ""

            with MeasureLatency(f"ai_inference_{self.fallback_provider}_fallback"):
                result = self._execute_chat(
                    messages, self.fallback_provider, fallback_key
                )

            result["_fallback_used"] = True
            return result
        finally:
            # Restore original provider
            self.provider = original_provider
            self.api_key = original_key
            self.model = original_model
            self.base_url = original_base_url

    def _execute_chat(
        self, messages: List[Dict[str, str]], provider: str, api_key: str
    ) -> Dict[str, Any]:
        """Execute chat with specified provider and key"""
        if provider == "openai":
            return self._chat_openai(messages, api_key)
        if provider in ("gemini", "google"):
            return self._chat_gemini(messages, api_key)

        return {"error": f"unsupported provider: {provider}"}

    def _should_rotate_key(self, result: Dict[str, Any]) -> bool:
        """Check if we should rotate to next API key"""
        if not result.get("error"):
            return False

        status = result.get("status")
        # Rotate on quota (429) or rate limit (429)
        if status == 429:
            return True

        # Also rotate on 401 (invalid key)
        if status == 401:
            return True

        return False

    def _default_model(self, provider: str) -> str:
        if provider in ("gemini", "google"):
            return "gemini-1.5-flash"
        return "gpt-4o-mini"

    def _default_base_url(
        self,
        provider: str,
        env_openai_base: Optional[str] = None,
        env_gemini_base: Optional[str] = None,
        settings_openai_base: Optional[str] = None,
        settings_gemini_base: Optional[str] = None,
    ) -> str:
        if provider in ("gemini", "google"):
            return (
                env_gemini_base
                or settings_gemini_base
                or "https://generativelanguage.googleapis.com/v1beta"
            )
        return env_openai_base or settings_openai_base or "https://api.openai.com/v1"

    def _resolve_all_api_keys(
        self, provider: str, settings: Optional[Any] = None
    ) -> List[str]:
        """Resolve all available API keys for a provider (primary + backups)"""
        keys = []

        if provider in ("gemini", "google"):
            # Primary key
            primary = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not primary and settings:
                primary = getattr(settings, "GEMINI_API_KEY", None)
            if primary:
                keys.append(primary)

            # Backup keys
            for i in [2, 3]:
                backup = os.getenv(f"GEMINI_API_KEY_{i}")
                if not backup and settings:
                    backup = getattr(settings, f"GEMINI_API_KEY_{i}", None)
                if backup:
                    keys.append(backup)
        else:  # openai
            # Primary key
            primary = os.getenv("OPENAI_API_KEY")
            if not primary and settings:
                primary = getattr(settings, "OPENAI_API_KEY", None)
            if primary:
                keys.append(primary)

            # Backup keys
            for i in [2, 3]:
                backup = os.getenv(f"OPENAI_API_KEY_{i}")
                if not backup and settings:
                    backup = getattr(settings, f"OPENAI_API_KEY_{i}", None)
                if backup:
                    keys.append(backup)

        return keys

    def _load_settings(self) -> Optional[Any]:
        try:
            from src.core.config import settings

            return settings
        except Exception:
            return None

    def _chat_openai(
        self, messages: List[Dict[str, str]], api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        key = api_key or self.api_key
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }
        data = json.dumps(payload).encode("utf-8")
        url = f"{self.base_url}/chat/completions"
        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")

                # Track metrics if possible (heuristic based on response header or body?)
                # urllib doesn't give easy access to usage headers in simple call,
                # but we can parse the body for 'usage'

        except urllib.error.HTTPError as exc:
            return self._http_error("llm http error", exc)
        except urllib.error.URLError as exc:
            return {"error": "llm connection error", "reason": str(exc.reason)}

        result = self._parse_openai_response(body)

        # Track metrics
        if "raw" in result and "usage" in result["raw"]:
            usage = result["raw"]["usage"]
            self.metrics.track_tokens(
                model=self.model,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            )

        return result

    def _chat_gemini(
        self, messages: List[Dict[str, str]], api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        key = api_key or self.api_key
        system_texts = [
            m.get("content", "") for m in messages if m.get("role") == "system"
        ]
        system_instruction = None
        if system_texts:
            system_instruction = {
                "role": "system",
                "parts": [{"text": "\n".join(system_texts).strip()}],
            }

        contents = []
        for message in messages:
            role = message.get("role")
            if role == "system":
                continue
            gemini_role = "user" if role == "user" else "model"
            contents.append(
                {"role": gemini_role, "parts": [{"text": message.get("content", "")}]}
            )

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"temperature": 0.2},
        }
        if system_instruction:
            payload["system_instruction"] = system_instruction

        data = json.dumps(payload).encode("utf-8")
        url = f"{self.base_url}/models/{self.model}:generateContent?key={key}"
        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return self._http_error("llm http error", exc)
        except urllib.error.URLError as exc:
            return {"error": "llm connection error", "reason": str(exc.reason)}

        result = self._parse_gemini_response(body)

        # Metric tracking for Gemini (usageMetadata)
        if "raw" in result and "usageMetadata" in result["raw"]:
            usage = result["raw"]["usageMetadata"]
            self.metrics.track_tokens(
                model=self.model,
                prompt_tokens=usage.get("promptTokenCount", 0),
                completion_tokens=usage.get("candidatesTokenCount", 0),
            )

        return result

    def _http_error(self, message: str, exc: urllib.error.HTTPError) -> Dict[str, Any]:
        try:
            error_body = exc.read().decode("utf-8")
        except Exception:
            error_body = None
        return {
            "error": message,
            "status": exc.code,
            "body": error_body,
        }

    def _parse_openai_response(self, body: str) -> Dict[str, Any]:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return {"error": "llm response parse failed", "raw": body}

        content = None
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            pass

        return {"content": content, "raw": payload}

    def _parse_gemini_response(self, body: str) -> Dict[str, Any]:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return {"error": "llm response parse failed", "raw": body}

        content = None
        try:
            parts = payload["candidates"][0]["content"]["parts"]
            content = "".join(part.get("text", "") for part in parts)
        except (KeyError, IndexError, TypeError):
            pass

        return {"content": content, "raw": payload}


class AIClientFactory:
    @staticmethod
    def get_client(provider: str = "mock", **kwargs) -> AIClient:
        if provider in ("server", "remote"):
            from src.core.ai.remote import RemoteAIClient

            return RemoteAIClient(**kwargs)
        if provider in ("openai", "gemini", "google", "auto"):
            # Pass provider to the generic client
            return LLMClient(provider=provider, **kwargs)
        return MockAIClient()
