"""
Monitoring Thresholds Configuration and Checking.

This module defines operational thresholds for the NSSS system and provides
utilities to check metrics against these thresholds to trigger alerts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AlertLevel(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class TokenThreshold:
    """Token usage thresholds."""

    # Per-request limits
    max_tokens_per_request: int = 8000
    warning_tokens_per_request: int = 6000

    # Per-scan limits (total across all LLM calls)
    max_tokens_per_scan: int = 100_000
    warning_tokens_per_scan: int = 75_000

    # Cost-based thresholds (for cloud providers)
    # Based on GPT-4 pricing: ~$0.03/1K input tokens, ~$0.06/1K output tokens
    max_cost_per_scan_usd: float = 5.0
    warning_cost_per_scan_usd: float = 3.0


@dataclass(frozen=True)
class LatencyThreshold:
    """Latency thresholds for different operations."""

    # Stage-specific thresholds (milliseconds)
    max_parse_latency_ms: float = 5000
    warning_parse_latency_ms: float = 3000

    max_cfg_build_latency_ms: float = 10000
    warning_cfg_build_latency_ms: float = 7000

    max_llm_call_latency_ms: float = 30000
    warning_llm_call_latency_ms: float = 20000

    max_total_scan_latency_ms: float = 120000  # 2 minutes
    warning_total_scan_latency_ms: float = 90000  # 1.5 minutes


@dataclass(frozen=True)
class QualityThreshold:
    """Quality metrics thresholds (precision, FPR)."""

    # False Positive Rate thresholds
    max_fpr: float = 0.30  # 30% FPR is critical
    warning_fpr: float = 0.20  # 20% FPR is warning

    # Precision thresholds
    min_precision: float = 0.70  # Below 70% is critical
    warning_precision: float = 0.80  # Below 80% is warning

    # Recall thresholds
    min_recall: float = 0.60  # Below 60% is critical
    warning_recall: float = 0.70  # Below 70% is warning


@dataclass(frozen=True)
class MonitoringThresholds:
    """Complete monitoring thresholds configuration."""

    token: TokenThreshold = TokenThreshold()
    latency: LatencyThreshold = LatencyThreshold()
    quality: QualityThreshold = QualityThreshold()

    @classmethod
    def from_config(
        cls, config: Optional[Dict[str, Any]] = None
    ) -> MonitoringThresholds:
        """Create thresholds from configuration dictionary."""
        if not config:
            return cls()

        token_config = config.get("token", {})
        latency_config = config.get("latency", {})
        quality_config = config.get("quality", {})

        return cls(
            token=TokenThreshold(**token_config) if token_config else TokenThreshold(),
            latency=LatencyThreshold(**latency_config)
            if latency_config
            else LatencyThreshold(),
            quality=QualityThreshold(**quality_config)
            if quality_config
            else QualityThreshold(),
        )


@dataclass
class Alert:
    """Represents a threshold violation alert."""

    level: AlertLevel
    category: str  # "token", "latency", "quality"
    metric: str  # Specific metric name
    value: float
    threshold: float
    message: str
    timestamp: float


class ThresholdChecker:
    """
    Checks metrics against configured thresholds and generates alerts.
    """

    def __init__(self, thresholds: Optional[MonitoringThresholds] = None):
        self.thresholds = thresholds or MonitoringThresholds()
        self.alerts: List[Alert] = []

    def check_token_usage(
        self, prompt_tokens: int, completion_tokens: int, scan_total_tokens: int = 0
    ) -> List[Alert]:
        """
        Check token usage against thresholds.

        Args:
            prompt_tokens: Tokens in the request prompt
            completion_tokens: Tokens in the response
            scan_total_tokens: Total tokens used in the entire scan so far

        Returns:
            List of alerts generated
        """
        alerts = []
        total_request_tokens = prompt_tokens + completion_tokens

        # Check per-request limits
        if total_request_tokens >= self.thresholds.token.max_tokens_per_request:
            alerts.append(
                self._create_alert(
                    AlertLevel.CRITICAL,
                    "token",
                    "tokens_per_request",
                    total_request_tokens,
                    self.thresholds.token.max_tokens_per_request,
                    f"LLM request exceeded max tokens: {total_request_tokens} "
                    f"(limit: {self.thresholds.token.max_tokens_per_request})",
                )
            )
        elif total_request_tokens >= self.thresholds.token.warning_tokens_per_request:
            alerts.append(
                self._create_alert(
                    AlertLevel.WARNING,
                    "token",
                    "tokens_per_request",
                    total_request_tokens,
                    self.thresholds.token.warning_tokens_per_request,
                    f"LLM request approaching token limit: {total_request_tokens} "
                    f"(warning threshold: {self.thresholds.token.warning_tokens_per_request})",
                )
            )

        # Check per-scan limits (if provided)
        if scan_total_tokens > 0:
            if scan_total_tokens >= self.thresholds.token.max_tokens_per_scan:
                alerts.append(
                    self._create_alert(
                        AlertLevel.CRITICAL,
                        "token",
                        "tokens_per_scan",
                        scan_total_tokens,
                        self.thresholds.token.max_tokens_per_scan,
                        f"Scan exceeded max total tokens: {scan_total_tokens} "
                        f"(limit: {self.thresholds.token.max_tokens_per_scan})",
                    )
                )
            elif scan_total_tokens >= self.thresholds.token.warning_tokens_per_scan:
                alerts.append(
                    self._create_alert(
                        AlertLevel.WARNING,
                        "token",
                        "tokens_per_scan",
                        scan_total_tokens,
                        self.thresholds.token.warning_tokens_per_scan,
                        f"Scan approaching total token limit: {scan_total_tokens} "
                        f"(warning threshold: {self.thresholds.token.warning_tokens_per_scan})",
                    )
                )

        self.alerts.extend(alerts)
        return alerts

    def check_latency(self, operation: str, duration_ms: float) -> List[Alert]:
        """
        Check operation latency against thresholds.

        Args:
            operation: Operation name (e.g., "parse", "cfg_build", "llm_call", "total_scan")
            duration_ms: Duration in milliseconds

        Returns:
            List of alerts generated
        """
        alerts = []
        op_lower = operation.lower()

        # Map operation to thresholds
        threshold_map = {
            "parse": (
                self.thresholds.latency.max_parse_latency_ms,
                self.thresholds.latency.warning_parse_latency_ms,
            ),
            "cfg_build": (
                self.thresholds.latency.max_cfg_build_latency_ms,
                self.thresholds.latency.warning_cfg_build_latency_ms,
            ),
            "llm_call": (
                self.thresholds.latency.max_llm_call_latency_ms,
                self.thresholds.latency.warning_llm_call_latency_ms,
            ),
            "total_scan": (
                self.thresholds.latency.max_total_scan_latency_ms,
                self.thresholds.latency.warning_total_scan_latency_ms,
            ),
        }

        max_latency, warning_latency = threshold_map.get(op_lower, (None, None))

        if max_latency is None:
            # Unknown operation, skip checking
            return alerts

        if duration_ms >= max_latency:
            alerts.append(
                self._create_alert(
                    AlertLevel.CRITICAL,
                    "latency",
                    operation,
                    duration_ms,
                    max_latency,
                    f"{operation} exceeded max latency: {duration_ms:.0f}ms "
                    f"(limit: {max_latency:.0f}ms)",
                )
            )
        elif duration_ms >= warning_latency:
            alerts.append(
                self._create_alert(
                    AlertLevel.WARNING,
                    "latency",
                    operation,
                    duration_ms,
                    warning_latency,
                    f"{operation} approaching latency limit: {duration_ms:.0f}ms "
                    f"(warning threshold: {warning_latency:.0f}ms)",
                )
            )

        self.alerts.extend(alerts)
        return alerts

    def check_quality_metrics(
        self, precision: float, recall: float, fpr: float
    ) -> List[Alert]:
        """
        Check quality metrics against thresholds.

        Args:
            precision: Precision score (0.0 - 1.0)
            recall: Recall score (0.0 - 1.0)
            fpr: False Positive Rate (0.0 - 1.0)

        Returns:
            List of alerts generated
        """
        alerts = []

        # Check FPR
        if fpr >= self.thresholds.quality.max_fpr:
            alerts.append(
                self._create_alert(
                    AlertLevel.CRITICAL,
                    "quality",
                    "fpr",
                    fpr,
                    self.thresholds.quality.max_fpr,
                    f"False Positive Rate is critically high: {fpr:.2%} "
                    f"(max: {self.thresholds.quality.max_fpr:.2%})",
                )
            )
        elif fpr >= self.thresholds.quality.warning_fpr:
            alerts.append(
                self._create_alert(
                    AlertLevel.WARNING,
                    "quality",
                    "fpr",
                    fpr,
                    self.thresholds.quality.warning_fpr,
                    f"False Positive Rate is elevated: {fpr:.2%} "
                    f"(warning threshold: {self.thresholds.quality.warning_fpr:.2%})",
                )
            )

        # Check precision
        if precision <= self.thresholds.quality.min_precision:
            alerts.append(
                self._create_alert(
                    AlertLevel.CRITICAL,
                    "quality",
                    "precision",
                    precision,
                    self.thresholds.quality.min_precision,
                    f"Precision is critically low: {precision:.2%} "
                    f"(min: {self.thresholds.quality.min_precision:.2%})",
                )
            )
        elif precision <= self.thresholds.quality.warning_precision:
            alerts.append(
                self._create_alert(
                    AlertLevel.WARNING,
                    "quality",
                    "precision",
                    precision,
                    self.thresholds.quality.warning_precision,
                    f"Precision is below target: {precision:.2%} "
                    f"(warning threshold: {self.thresholds.quality.warning_precision:.2%})",
                )
            )

        # Check recall
        if recall <= self.thresholds.quality.min_recall:
            alerts.append(
                self._create_alert(
                    AlertLevel.CRITICAL,
                    "quality",
                    "recall",
                    recall,
                    self.thresholds.quality.min_recall,
                    f"Recall is critically low: {recall:.2%} "
                    f"(min: {self.thresholds.quality.min_recall:.2%})",
                )
            )
        elif recall <= self.thresholds.quality.warning_recall:
            alerts.append(
                self._create_alert(
                    AlertLevel.WARNING,
                    "quality",
                    "recall",
                    recall,
                    self.thresholds.quality.warning_recall,
                    f"Recall is below target: {recall:.2%} "
                    f"(warning threshold: {self.thresholds.quality.warning_recall:.2%})",
                )
            )

        self.alerts.extend(alerts)
        return alerts

    def _create_alert(
        self,
        level: AlertLevel,
        category: str,
        metric: str,
        value: float,
        threshold: float,
        message: str,
    ) -> Alert:
        """Create an alert and log it."""
        import time

        alert = Alert(
            level=level,
            category=category,
            metric=metric,
            value=value,
            threshold=threshold,
            message=message,
            timestamp=time.time(),
        )

        if level == AlertLevel.CRITICAL:
            logger.critical(f"THRESHOLD VIOLATION: {message}")
        elif level == AlertLevel.WARNING:
            logger.warning(f"THRESHOLD WARNING: {message}")
        else:
            logger.info(f"THRESHOLD INFO: {message}")

        return alert

    def get_alerts(
        self, level: Optional[AlertLevel] = None, category: Optional[str] = None
    ) -> List[Alert]:
        """
        Get all alerts, optionally filtered by level and category.

        Args:
            level: Filter by alert level (INFO, WARNING, CRITICAL)
            category: Filter by category (token, latency, quality)

        Returns:
            Filtered list of alerts
        """
        alerts = self.alerts

        if level:
            alerts = [a for a in alerts if a.level == level]

        if category:
            alerts = [a for a in alerts if a.category == category]

        return alerts

    def clear_alerts(self):
        """Clear all recorded alerts."""
        self.alerts.clear()


# Singleton instance for global access
_default_checker: Optional[ThresholdChecker] = None


def get_threshold_checker() -> ThresholdChecker:
    """Get the global threshold checker instance."""
    global _default_checker
    if _default_checker is None:
        _default_checker = ThresholdChecker()
    return _default_checker


def reset_threshold_checker(thresholds: Optional[MonitoringThresholds] = None):
    """Reset the global threshold checker with new thresholds."""
    global _default_checker
    _default_checker = ThresholdChecker(thresholds)
