import json
import logging
import io
import pytest
from src.core.telemetry.logger import setup_logging, get_logger, JSONFormatter


def test_json_formatter():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    data = json.loads(formatted)

    assert data["message"] == "Test message"
    assert data["level"] == "INFO"
    assert data["logger"] == "test_logger"
    assert "timestamp" in data


def test_logger_integration(capsys):
    # Setup logging to capture output
    setup_logging(level="INFO")
    logger = get_logger("integration_test")

    logger.info("Info message", extra={"user_id": 123})

    captured = capsys.readouterr()
    output = captured.err  # logging default goes to stderr

    # Depending on pytest capture, it might be in err.
    # If standard logging setup uses StreamHandler without target, it goes to stderr.

    # Let's parse the last line
    lines = output.strip().split("\n")
    assert len(lines) > 0
    last_line = lines[-1]

    try:
        data = json.loads(last_line)
        assert data["message"] == "Info message"
        assert data["user_id"] == 123
        assert data["level"] == "INFO"
    except json.JSONDecodeError:
        pytest.fail(f"Output was not JSON: {last_line}")


def test_exception_logging():
    formatter = JSONFormatter()
    try:
        raise ValueError("Test error")
    except ValueError:
        import sys

        record = logging.LogRecord(
            name="test_error",
            level=logging.ERROR,
            pathname="test.py",
            lineno=20,
            msg="Error occurred",
            args=(),
            exc_info=sys.exc_info(),
        )
        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert data["message"] == "Error occurred"
        assert "exception" in data
        assert "ValueError: Test error" in data["exception"]
