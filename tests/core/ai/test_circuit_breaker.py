from src.core.ai.circuit_breaker import CircuitBreaker, CircuitState


def test_breaker_opens_after_failures() -> None:
    breaker = CircuitBreaker(
        failure_threshold=2, recovery_timeout_seconds=10.0, time_fn=lambda: 0.0
    )

    assert breaker.allow_request() is True
    breaker.record_failure()
    assert breaker.state() == CircuitState.CLOSED
    breaker.record_failure()
    assert breaker.state() == CircuitState.OPEN
    assert breaker.allow_request() is False


def test_breaker_half_open_then_closes_on_success() -> None:
    now = [0.0]

    def time_fn() -> float:
        return now[0]

    breaker = CircuitBreaker(
        failure_threshold=1,
        recovery_timeout_seconds=5.0,
        half_open_success_threshold=1,
        time_fn=time_fn,
    )

    breaker.record_failure()
    assert breaker.state() == CircuitState.OPEN
    assert breaker.allow_request() is False

    now[0] = 5.0
    assert breaker.allow_request() is True
    assert breaker.state() == CircuitState.HALF_OPEN

    breaker.record_success()
    assert breaker.state() == CircuitState.CLOSED
    assert breaker.allow_request() is True


def test_breaker_half_open_failure_reopens() -> None:
    now = [0.0]

    def time_fn() -> float:
        return now[0]

    breaker = CircuitBreaker(
        failure_threshold=1, recovery_timeout_seconds=1.0, time_fn=time_fn
    )

    breaker.record_failure()
    assert breaker.state() == CircuitState.OPEN

    now[0] = 1.0
    assert breaker.allow_request() is True
    assert breaker.state() == CircuitState.HALF_OPEN

    breaker.record_failure()
    assert breaker.state() == CircuitState.OPEN
