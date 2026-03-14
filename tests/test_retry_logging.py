"""Unit tests for retry_logging: call_with_retry and compliance log events."""
import threading
import time
import pytest

from codes.retry_logging import (
    call_with_retry,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_BACKOFF_BASE_SEC,
    DEFAULT_MAX_BACKOFF_SEC,
)


class TestCallWithRetrySuccess:
    """call_with_retry returns result when fn succeeds."""

    def test_success_first_try(self):
        result = call_with_retry(lambda: 42, name="test", stage="test_stage")
        assert result == 42

    def test_success_with_args_kwargs(self):
        result = call_with_retry(
            lambda x, y, *, z=0: x + y + z,
            1, 2, name="test", stage="test_stage", z=3
        )
        assert result == 6

    def test_success_after_one_failure(self, monkeypatch):
        monkeypatch.setattr("codes.retry_logging.time.sleep", lambda _: None)
        attempts = []

        def flaky():
            attempts.append(1)
            if len(attempts) < 2:
                raise ValueError("temporary")
            return "ok"

        result = call_with_retry(flaky, name="flaky", stage="test", max_attempts=3)
        assert result == "ok"
        assert len(attempts) == 2


class TestCallWithRetryExhausted:
    """call_with_retry raises after max_attempts and logs retry_exhausted."""

    def test_raises_after_max_attempts(self):
        def fail():
            raise RuntimeError("always fails")

        with pytest.raises(RuntimeError, match="always fails"):
            call_with_retry(fail, name="fail", stage="test", max_attempts=2)

    def test_retry_attempt_and_retry_exhausted_logged(self, monkeypatch):
        monkeypatch.setattr("codes.retry_logging.time.sleep", lambda _: None)
        log_calls = []

        def capture_log(event_type, stage, message, **kw):
            log_calls.append({"event_type": event_type, "stage": stage, "message": message, **kw})

        import codes.retry_logging as mod
        monkeypatch.setattr(mod, "_log", capture_log)

        def fail():
            raise ValueError("err")

        with pytest.raises(ValueError):
            call_with_retry(fail, name="op", stage="myspace", max_attempts=3)

        retry_attempts = [c for c in log_calls if c["event_type"] == "retry_attempt"]
        exhausted = [c for c in log_calls if c["event_type"] == "retry_exhausted"]
        assert len(retry_attempts) == 2  # after attempt 1 and 2
        assert len(exhausted) == 1
        assert exhausted[0]["stage"] == "myspace"
        assert "after 3 attempts" in exhausted[0]["message"]
        assert exhausted[0].get("error") == "err"
        assert exhausted[0].get("metadata", {}).get("operation") == "op"


class TestCallWithRetryConfig:
    """Default and custom retry config."""

    def test_default_constants(self):
        assert DEFAULT_MAX_ATTEMPTS == 3
        assert DEFAULT_BACKOFF_BASE_SEC == 1
        assert DEFAULT_MAX_BACKOFF_SEC == 60

    def test_custom_max_attempts(self, monkeypatch):
        monkeypatch.setattr("codes.retry_logging.time.sleep", lambda _: None)
        count = 0

        def fail_twice():
            nonlocal count
            count += 1
            if count < 3:
                raise OSError("retry")
            return 1

        result = call_with_retry(fail_twice, name="x", stage="y", max_attempts=5)
        assert result == 1
        assert count == 3


class TestCallWithRetryTimeout:
    """call_with_retry with timeout_seconds raises TimeoutError when fn exceeds timeout."""

    def test_timeout_raises_after_expiry(self, monkeypatch):
        monkeypatch.setattr("codes.retry_logging.time.sleep", lambda _: None)
        # Block until an event so the executor hits timeout (event never set)
        block = threading.Event()

        def slow():
            block.wait()  # blocks until set; never set so timeout triggers
            return 1

        with pytest.raises(TimeoutError, match="timed out"):
            call_with_retry(slow, name="slow", stage="test", timeout_seconds=0.1, max_attempts=2)

    def test_no_timeout_succeeds_without_time_limit(self):
        result = call_with_retry(lambda: 99, name="fast", stage="test", timeout_seconds=None)
        assert result == 99
