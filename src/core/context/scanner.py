from dataclasses import dataclass
from enum import Enum
from typing import List, Any
from src.core.context.loader import ProjectContext


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class ConfigIssue:
    key: str
    severity: Severity
    message: str
    remediation: str


class ConfigScanner:
    """Scans project configuration (settings, env) for security risks."""

    def scan(self, context: ProjectContext) -> List[ConfigIssue]:
        issues = []

        # 1. Check DEBUG mode
        if self._is_debug_enabled(context):
            issues.append(
                ConfigIssue(
                    key="DEBUG",
                    severity=Severity.HIGH,
                    message="DEBUG mode is enabled in production configuration.",
                    remediation="Set DEBUG=False in settings.py or .env for production environments.",
                )
            )

        # 2. Check SECRET_KEY
        secret_key = self._get_config_value(context, "SECRET_KEY")
        if not secret_key:
            issues.append(
                ConfigIssue(
                    key="SECRET_KEY",
                    severity=Severity.CRITICAL,
                    message="SECRET_KEY is missing.",
                    remediation="Define a strong SECRET_KEY in .env or settings.py.",
                )
            )
        elif len(str(secret_key)) < 32 or str(secret_key) in [
            "django-insecure",
            "secret",
            "123456",
            "changeme",
        ]:
            issues.append(
                ConfigIssue(
                    key="SECRET_KEY",
                    severity=Severity.CRITICAL,
                    message="Weak SECRET_KEY detected.",
                    remediation="Use a cryptographically strong random string (at least 32 chars).",
                )
            )

        # 3. Check CORS
        if self._is_cors_permissive(context):
            issues.append(
                ConfigIssue(
                    key="CORS",
                    severity=Severity.HIGH,
                    message="CORS configuration allows all origins ('*').",
                    remediation="Restrict CORS_ALLOWED_ORIGINS to specific trusted domains.",
                )
            )

        return issues

    def _get_config_value(self, context: ProjectContext, key: str) -> Any:
        """Helper to get value from env or settings (env takes precedence)."""
        if key in context.env_vars:
            return context.env_vars[key]
        return context.settings.get(key)

    def _is_debug_enabled(self, context: ProjectContext) -> bool:
        val = self._get_config_value(context, "DEBUG")
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes", "on")
        return False

    def _is_cors_permissive(self, context: ProjectContext) -> bool:
        # Check standard Django/Flask CORS settings
        allow_all = self._get_config_value(context, "CORS_ALLOW_ALL_ORIGINS")
        if allow_all is True:
            return True
        if isinstance(allow_all, str) and allow_all.lower() == "true":
            return True

        allow_origins = self._get_config_value(context, "CORS_ALLOWED_ORIGINS")
        if allow_origins == "*" or (
            isinstance(allow_origins, list) and "*" in allow_origins
        ):
            return True

        return False
