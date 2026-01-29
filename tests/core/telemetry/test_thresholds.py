"""Tests for monitoring thresholds and alerting."""

from src.core.telemetry.thresholds import (
    AlertLevel,
    LatencyThreshold,
    MonitoringThresholds,
    QualityThreshold,
    ThresholdChecker,
    TokenThreshold,
)


class TestTokenThreshold:
    """Test token threshold configuration."""

    def test_default_values(self):
        """Test default token threshold values."""
        threshold = TokenThreshold()
        assert threshold.max_tokens_per_request == 8000
        assert threshold.warning_tokens_per_request == 6000
        assert threshold.max_tokens_per_scan == 100_000
        assert threshold.warning_tokens_per_scan == 75_000

    def test_custom_values(self):
        """Test custom token threshold values."""
        threshold = TokenThreshold(
            max_tokens_per_request=10000,
            warning_tokens_per_request=8000,
            max_tokens_per_scan=200_000,
            warning_tokens_per_scan=150_000,
        )
        assert threshold.max_tokens_per_request == 10000
        assert threshold.warning_tokens_per_request == 8000


class TestLatencyThreshold:
    """Test latency threshold configuration."""

    def test_default_values(self):
        """Test default latency threshold values."""
        threshold = LatencyThreshold()
        assert threshold.max_parse_latency_ms == 5000
        assert threshold.warning_parse_latency_ms == 3000
        assert threshold.max_llm_call_latency_ms == 30000
        assert threshold.warning_llm_call_latency_ms == 20000


class TestQualityThreshold:
    """Test quality metrics threshold configuration."""

    def test_default_values(self):
        """Test default quality threshold values."""
        threshold = QualityThreshold()
        assert threshold.max_fpr == 0.30
        assert threshold.warning_fpr == 0.20
        assert threshold.min_precision == 0.70
        assert threshold.warning_precision == 0.80


class TestMonitoringThresholds:
    """Test complete monitoring thresholds configuration."""

    def test_default_thresholds(self):
        """Test default monitoring thresholds."""
        thresholds = MonitoringThresholds()
        assert isinstance(thresholds.token, TokenThreshold)
        assert isinstance(thresholds.latency, LatencyThreshold)
        assert isinstance(thresholds.quality, QualityThreshold)

    def test_from_config_empty(self):
        """Test creating thresholds from empty config."""
        thresholds = MonitoringThresholds.from_config(None)
        assert isinstance(thresholds.token, TokenThreshold)

    def test_from_config_partial(self):
        """Test creating thresholds from partial config."""
        config = {"token": {"max_tokens_per_request": 12000}}
        thresholds = MonitoringThresholds.from_config(config)
        assert thresholds.token.max_tokens_per_request == 12000
        # Other values should use defaults
        assert thresholds.token.warning_tokens_per_request == 6000


class TestThresholdChecker:
    """Test threshold checking and alerting logic."""

    def test_token_usage_within_limits(self):
        """Test token usage within limits generates no alerts."""
        checker = ThresholdChecker()
        alerts = checker.check_token_usage(1000, 500)
        assert len(alerts) == 0

    def test_token_usage_warning_level(self):
        """Test token usage at warning level."""
        checker = ThresholdChecker()
        alerts = checker.check_token_usage(4000, 2500)  # 6500 total
        assert len(alerts) == 1
        assert alerts[0].level == AlertLevel.WARNING
        assert alerts[0].category == "token"
        assert alerts[0].metric == "tokens_per_request"

    def test_token_usage_critical_level(self):
        """Test token usage at critical level."""
        checker = ThresholdChecker()
        alerts = checker.check_token_usage(6000, 3000)  # 9000 total
        assert len(alerts) == 1
        assert alerts[0].level == AlertLevel.CRITICAL
        assert alerts[0].category == "token"

    def test_scan_token_usage_warning(self):
        """Test scan-wide token usage warning."""
        checker = ThresholdChecker()
        alerts = checker.check_token_usage(1000, 500, scan_total_tokens=76000)
        assert len(alerts) == 1
        assert alerts[0].level == AlertLevel.WARNING
        assert alerts[0].metric == "tokens_per_scan"

    def test_scan_token_usage_critical(self):
        """Test scan-wide token usage critical."""
        checker = ThresholdChecker()
        alerts = checker.check_token_usage(1000, 500, scan_total_tokens=101000)
        assert len(alerts) == 1
        assert alerts[0].level == AlertLevel.CRITICAL
        assert alerts[0].metric == "tokens_per_scan"

    def test_latency_within_limits(self):
        """Test latency within limits generates no alerts."""
        checker = ThresholdChecker()
        alerts = checker.check_latency("parse", 2000)
        assert len(alerts) == 0

    def test_latency_warning_level(self):
        """Test latency at warning level."""
        checker = ThresholdChecker()
        alerts = checker.check_latency("parse", 3500)
        assert len(alerts) == 1
        assert alerts[0].level == AlertLevel.WARNING
        assert alerts[0].category == "latency"
        assert alerts[0].metric == "parse"

    def test_latency_critical_level(self):
        """Test latency at critical level."""
        checker = ThresholdChecker()
        alerts = checker.check_latency("llm_call", 35000)
        assert len(alerts) == 1
        assert alerts[0].level == AlertLevel.CRITICAL
        assert alerts[0].category == "latency"

    def test_latency_unknown_operation(self):
        """Test latency check for unknown operation."""
        checker = ThresholdChecker()
        alerts = checker.check_latency("unknown_op", 50000)
        # Should not generate alerts for unknown operations
        assert len(alerts) == 0

    def test_quality_metrics_good(self):
        """Test quality metrics within acceptable range."""
        checker = ThresholdChecker()
        alerts = checker.check_quality_metrics(precision=0.85, recall=0.80, fpr=0.15)
        assert len(alerts) == 0

    def test_quality_fpr_warning(self):
        """Test FPR at warning level."""
        checker = ThresholdChecker()
        alerts = checker.check_quality_metrics(precision=0.85, recall=0.80, fpr=0.25)
        assert len(alerts) == 1
        assert alerts[0].level == AlertLevel.WARNING
        assert alerts[0].metric == "fpr"

    def test_quality_fpr_critical(self):
        """Test FPR at critical level."""
        checker = ThresholdChecker()
        alerts = checker.check_quality_metrics(precision=0.85, recall=0.80, fpr=0.35)
        assert len(alerts) == 1
        assert alerts[0].level == AlertLevel.CRITICAL
        assert alerts[0].metric == "fpr"

    def test_quality_precision_warning(self):
        """Test precision at warning level."""
        checker = ThresholdChecker()
        alerts = checker.check_quality_metrics(precision=0.75, recall=0.80, fpr=0.15)
        assert len(alerts) == 1
        assert alerts[0].level == AlertLevel.WARNING
        assert alerts[0].metric == "precision"

    def test_quality_precision_critical(self):
        """Test precision at critical level."""
        checker = ThresholdChecker()
        alerts = checker.check_quality_metrics(precision=0.65, recall=0.80, fpr=0.15)
        assert len(alerts) == 1
        assert alerts[0].level == AlertLevel.CRITICAL
        assert alerts[0].metric == "precision"

    def test_quality_recall_warning(self):
        """Test recall at warning level."""
        checker = ThresholdChecker()
        alerts = checker.check_quality_metrics(precision=0.85, recall=0.65, fpr=0.15)
        assert len(alerts) == 1
        assert alerts[0].level == AlertLevel.WARNING
        assert alerts[0].metric == "recall"

    def test_quality_recall_critical(self):
        """Test recall at critical level."""
        checker = ThresholdChecker()
        alerts = checker.check_quality_metrics(precision=0.85, recall=0.55, fpr=0.15)
        assert len(alerts) == 1
        assert alerts[0].level == AlertLevel.CRITICAL
        assert alerts[0].metric == "recall"

    def test_multiple_alerts(self):
        """Test multiple alerts generated simultaneously."""
        checker = ThresholdChecker()

        # Generate multiple alerts
        checker.check_token_usage(6000, 3000)  # Critical
        checker.check_latency("parse", 6000)  # Critical
        checker.check_quality_metrics(
            precision=0.65, recall=0.55, fpr=0.35
        )  # 3 critical

        all_alerts = checker.get_alerts()
        assert len(all_alerts) == 5

        # All should be critical
        critical_alerts = checker.get_alerts(level=AlertLevel.CRITICAL)
        assert len(critical_alerts) == 5

    def test_get_alerts_by_category(self):
        """Test filtering alerts by category."""
        checker = ThresholdChecker()

        checker.check_token_usage(6000, 3000)  # Token alert
        checker.check_latency("parse", 6000)  # Latency alert
        checker.check_quality_metrics(
            precision=0.65, recall=0.80, fpr=0.15
        )  # Quality alert

        token_alerts = checker.get_alerts(category="token")
        assert len(token_alerts) == 1
        assert token_alerts[0].category == "token"

        latency_alerts = checker.get_alerts(category="latency")
        assert len(latency_alerts) == 1
        assert latency_alerts[0].category == "latency"

    def test_clear_alerts(self):
        """Test clearing alerts."""
        checker = ThresholdChecker()

        checker.check_token_usage(6000, 3000)
        assert len(checker.get_alerts()) == 1

        checker.clear_alerts()
        assert len(checker.get_alerts()) == 0

    def test_alert_contains_metadata(self):
        """Test that alerts contain all required metadata."""
        checker = ThresholdChecker()
        alerts = checker.check_token_usage(6000, 3000)

        alert = alerts[0]
        assert hasattr(alert, "level")
        assert hasattr(alert, "category")
        assert hasattr(alert, "metric")
        assert hasattr(alert, "value")
        assert hasattr(alert, "threshold")
        assert hasattr(alert, "message")
        assert hasattr(alert, "timestamp")
        assert isinstance(alert.timestamp, float)
        assert alert.timestamp > 0


class TestCustomThresholds:
    """Test using custom threshold values."""

    def test_custom_token_thresholds(self):
        """Test checker with custom token thresholds."""
        custom_thresholds = MonitoringThresholds(
            token=TokenThreshold(max_tokens_per_request=5000)
        )
        checker = ThresholdChecker(custom_thresholds)

        alerts = checker.check_token_usage(3000, 2500)  # 5500 total
        assert len(alerts) == 1
        assert alerts[0].level == AlertLevel.CRITICAL

    def test_custom_latency_thresholds(self):
        """Test checker with custom latency thresholds."""
        custom_thresholds = MonitoringThresholds(
            latency=LatencyThreshold(max_parse_latency_ms=2000)
        )
        checker = ThresholdChecker(custom_thresholds)

        alerts = checker.check_latency("parse", 2500)
        assert len(alerts) == 1
        assert alerts[0].level == AlertLevel.CRITICAL

    def test_custom_quality_thresholds(self):
        """Test checker with custom quality thresholds."""
        custom_thresholds = MonitoringThresholds(
            quality=QualityThreshold(min_precision=0.90)
        )
        checker = ThresholdChecker(custom_thresholds)

        alerts = checker.check_quality_metrics(precision=0.85, recall=0.80, fpr=0.15)
        assert len(alerts) == 1
        assert alerts[0].level == AlertLevel.CRITICAL
        assert alerts[0].metric == "precision"
