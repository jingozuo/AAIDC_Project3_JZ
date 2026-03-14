"""
Retry with exponential backoff and structured logging for tool/LLM failures.

All retry attempts and final failures are logged to the same compliance log
(logs/guardrails_compliance.jsonl) via guardrails_safety.log_compliance for
debugging and traceability. Optional per-call timeout via timeout_seconds.
"""
import time
from concurrent.futures import TimeoutError as FuturesTimeoutError
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional, TypeVar

try:
    from guardrails_safety import log_compliance
except ModuleNotFoundError:
    try:
        from codes.guardrails_safety import log_compliance
    except ModuleNotFoundError:
        log_compliance = None  # no-op if guardrails_safety not importable


def _log(event_type: str, stage: str, message: str, **kw: Any) -> None:
    if log_compliance is not None:
        log_compliance(event_type, stage, message, **kw)

T = TypeVar("T")

# Default retry configuration
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_BASE_SEC = 1
DEFAULT_MAX_BACKOFF_SEC = 60


def call_with_retry(
    fn: Callable[..., T],
    *args: Any,
    name: str,
    stage: str = "workflow",
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_base: float = DEFAULT_BACKOFF_BASE_SEC,
    max_backoff: float = DEFAULT_MAX_BACKOFF_SEC,
    log_args_preview: Optional[str] = None,
    timeout_seconds: Optional[float] = None,
    **kwargs: Any,
) -> T:
    """
    Call fn(*args, **kwargs) with exponential backoff on exception.
    Log each retry attempt and final failure to the compliance log.
    If timeout_seconds is set, each attempt is limited to that duration.

    Args:
        fn: Callable to invoke (e.g. lookup_policy_in_csv, llm.invoke).
        *args: Positional arguments for fn.
        name: Short name for the operation (e.g. "data_lookup", "llm_invoke", "refund_logger").
        stage: Stage/location (e.g. "intake", "summary", "logger").
        max_attempts: Maximum number of attempts (default 3).
        backoff_base: Base seconds for exponential wait (default 1).
        max_backoff: Cap on wait seconds (default 60).
        log_args_preview: Optional string to log instead of full args (e.g. policy number).
        timeout_seconds: Optional per-call timeout in seconds; raises TimeoutError on expiry.
        **kwargs: Keyword arguments for fn.

    Returns:
        Result of fn(*args, **kwargs).

    Raises:
        Re-raises the last exception (or TimeoutError) after all attempts and logging.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        last_exc = None
        err_str = ""
        try:
            if timeout_seconds is not None and timeout_seconds > 0:
                ex = ThreadPoolExecutor(max_workers=1)
                try:
                    fut = ex.submit(fn, *args, **kwargs)
                    return fut.result(timeout=timeout_seconds)
                finally:
                    ex.shutdown(wait=False)  # avoid blocking on timeout when worker still running
            return fn(*args, **kwargs)
        except FuturesTimeoutError as e:
            last_exc = TimeoutError(f"Operation {name} timed out after {timeout_seconds}s")
            last_exc.__cause__ = e
            err_str = str(last_exc)
        except Exception as e:
            last_exc = e
            err_str = str(e) if e else ""
        if last_exc is not None:
            if attempt < max_attempts:
                wait_sec = min(backoff_base ** attempt, max_backoff)
                _log(
                    "retry_attempt",
                    stage,
                    f"{name} failed (attempt {attempt}/{max_attempts}), retrying in {wait_sec:.1f}s",
                    error=err_str[:500] if err_str else None,
                    metadata={
                        "operation": name,
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "wait_seconds": wait_sec,
                        "args_preview": log_args_preview,
                    },
                )
                time.sleep(wait_sec)
            else:
                _log(
                    "retry_exhausted",
                    stage,
                    f"{name} failed after {max_attempts} attempts",
                    error=err_str[:500] if err_str else None,
                    metadata={
                        "operation": name,
                        "attempts": max_attempts,
                        "args_preview": log_args_preview,
                    },
                )
                raise last_exc
    assert last_exc is not None
    raise last_exc
