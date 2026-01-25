import time
import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class LatencyRecord:
    operation: str
    duration_ms: float
    timestamp: float


class MetricsCollector:
    """
    Singleton class to collect telemetry metrics (latency, token usage).
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MetricsCollector, cls).__new__(cls)
            cls._instance.reset()
        return cls._instance

    def reset(self):
        """Resets all metrics."""
        self.token_usage: List[TokenUsage] = []
        self.latencies: List[LatencyRecord] = []
        # Aggregated stats
        self.token_counts: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"prompt": 0, "completion": 0, "total": 0}
        )
        self.latency_stats: Dict[str, List[float]] = defaultdict(list)

    def track_tokens(self, model: str, prompt_tokens: int, completion_tokens: int):
        """Records token usage for a specific model."""
        usage = TokenUsage(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
        self.token_usage.append(usage)

        self.token_counts[model]["prompt"] += prompt_tokens
        self.token_counts[model]["completion"] += completion_tokens
        self.token_counts[model]["total"] += usage.total_tokens

        logger.info(
            "Token usage recorded",
            extra={
                "metric_type": "tokens",
                "model": model,
                "prompt": prompt_tokens,
                "completion": completion_tokens,
                "total": usage.total_tokens,
            },
        )

    def track_latency(self, operation: str, duration_ms: float):
        """Records latency for an operation."""
        record = LatencyRecord(
            operation=operation, duration_ms=duration_ms, timestamp=time.time()
        )
        self.latencies.append(record)
        self.latency_stats[operation].append(duration_ms)

        logger.info(
            "Latency recorded",
            extra={
                "metric_type": "latency",
                "operation": operation,
                "duration_ms": duration_ms,
            },
        )

    def get_summary(self) -> Dict[str, Any]:
        """Returns a summary of collected metrics."""
        summary = {"tokens": dict(self.token_counts), "latency": {}}

        for op, durations in self.latency_stats.items():
            if durations:
                summary["latency"][op] = {
                    "count": len(durations),
                    "min": min(durations),
                    "max": max(durations),
                    "avg": sum(durations) / len(durations),
                }

        return summary

    def dump_to_file(self, filepath: str):
        """Dumps metrics summary to a JSON file."""
        try:
            with open(filepath, "w") as f:
                json.dump(self.get_summary(), f, indent=2)
            logger.info(f"Metrics dumped to {filepath}")
        except Exception as e:
            logger.error(f"Failed to dump metrics: {str(e)}")


# Helper context manager for latency tracking
class MeasureLatency:
    def __init__(self, operation: str):
        self.operation = operation
        self.collector = MetricsCollector()
        self.start_time = 0

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000
        self.collector.track_latency(self.operation, duration_ms)
