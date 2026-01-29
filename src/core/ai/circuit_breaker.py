from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from threading import Lock
from time import monotonic
from typing import Callable, Dict, Optional
import logging


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True)
class CircuitBreakerConfig:
    failure_threshold: int = 3
    recovery_timeout_seconds: float = 30.0
    half_open_success_threshold: int = 1


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 30.0,
        half_open_success_threshold: int = 1,
        time_fn: Callable[[], float] = monotonic,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._failure_threshold = max(1, failure_threshold)
        self._recovery_timeout_seconds = max(0.0, recovery_timeout_seconds)
        self._half_open_success_threshold = max(1, half_open_success_threshold)
        self._time_fn = time_fn
        self._logger = logger or logging.getLogger(__name__)
        self._lock = Lock()

        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: Optional[float] = None
        self._half_open_successes = 0
        self._half_open_in_flight = False

    def allow_request(self) -> bool:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._opened_at is None:
                    return False
                elapsed = self._time_fn() - self._opened_at
                if elapsed >= self._recovery_timeout_seconds:
                    self._transition_to_half_open()
                    self._half_open_in_flight = True
                    return True
                return False

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_in_flight:
                    return False
                self._half_open_in_flight = True
                return True

            return True

    def record_success(self) -> None:
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_in_flight = False
                self._half_open_successes += 1
                if self._half_open_successes >= self._half_open_success_threshold:
                    self._transition_to_closed()
                return

            if self._state == CircuitState.CLOSED:
                self._failure_count = 0

    def record_failure(self) -> None:
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_in_flight = False
                self._transition_to_open()
                return

            if self._state == CircuitState.CLOSED:
                self._failure_count += 1
                if self._failure_count >= self._failure_threshold:
                    self._transition_to_open()

    def state(self) -> CircuitState:
        with self._lock:
            return self._state

    def _transition_to_open(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = self._time_fn()
        self._failure_count = 0
        self._half_open_successes = 0
        self._logger.warning("Circuit breaker opened")

    def _transition_to_half_open(self) -> None:
        self._state = CircuitState.HALF_OPEN
        self._opened_at = None
        self._half_open_successes = 0
        self._half_open_in_flight = False
        self._logger.info("Circuit breaker half-open")

    def _transition_to_closed(self) -> None:
        self._state = CircuitState.CLOSED
        self._opened_at = None
        self._failure_count = 0
        self._half_open_successes = 0
        self._half_open_in_flight = False
        self._logger.info("Circuit breaker closed")


class CircuitBreakerRegistry:
    _breakers: Dict[str, CircuitBreaker] = {}
    _lock: Lock = Lock()

    @classmethod
    def get_breaker(cls, key: str, config: CircuitBreakerConfig) -> CircuitBreaker:
        with cls._lock:
            if key in cls._breakers:
                return cls._breakers[key]
            breaker = CircuitBreaker(
                failure_threshold=config.failure_threshold,
                recovery_timeout_seconds=config.recovery_timeout_seconds,
                half_open_success_threshold=config.half_open_success_threshold,
            )
            cls._breakers[key] = breaker
            return breaker
