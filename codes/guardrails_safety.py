"""
Guardrails Hub–style input validation, output filtering, and compliance logging.

Provides:
  - Input validation and sanitization: user input (policy number, confirmations) sanitized and validated.
  - Output filtering and content safety: LLM notice text filtered (length, unsafe content); safe fallback on failure.
  - Error handling with graceful degradation: validation/guard failures log and return safe defaults instead of crashing.
  - Logging for compliance and debugging: structured JSONL log (guardrails_compliance.jsonl) for audits and debugging.

To add Guardrails Hub validators (e.g. PII, ToxicLanguage), install via `guardrails hub install <validator>`
and register in create_input_guard() / create_output_guard().
"""
import json
import os
import re
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

try:
    from codes.paths import LOGS_DIR, COMPLIANCE_LOG_PATH
except ModuleNotFoundError:
    from paths import LOGS_DIR, COMPLIANCE_LOG_PATH

# --- Constants ---
MAX_USER_INPUT_LENGTH = 500
MAX_NOTICE_TEXT_LENGTH = 10_000
POLICY_NUMBER_PATTERN = re.compile(r"^[A-Za-z0-9\-_\s]+$")  # alphanumeric, hyphen, underscore, spaces
SAFE_NOTICE_FALLBACK = "Your insurance cancellation has been processed. Please retain this notice for your records."


# --- Compliance logging ---
def _ensure_log_dir() -> None:
    os.makedirs(LOGS_DIR, exist_ok=True)


def log_compliance(
    event_type: str,
    stage: str,
    message: str,
    *,
    validated: Optional[bool] = None,
    raw_value: Optional[str] = None,
    sanitized_value: Optional[str] = None,
    error: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Append a structured compliance/debug entry to the guardrails log (JSONL).
    Use for input validation, output filtering, and error events.
    """
    _ensure_log_dir()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "stage": stage,
        "message": message,
    }
    if validated is not None:
        entry["validated"] = validated
    if raw_value is not None:
        entry["raw_value"] = raw_value[:200] + "..." if len(str(raw_value)) > 200 else raw_value
    if sanitized_value is not None:
        entry["sanitized_value"] = sanitized_value[:200] + "..." if len(str(sanitized_value)) > 200 else sanitized_value
    if error is not None:
        entry["error"] = error
    if metadata:
        entry["metadata"] = metadata
    try:
        with open(COMPLIANCE_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as e:
        logging.getLogger(__name__).warning("Guardrails compliance log write failed: %s", e)


# --- Input validation and sanitization ---
def sanitize_user_input(raw: str) -> str:
    """
    Sanitize user input: strip, limit length, remove control characters.
    Logs the sanitization for compliance. Graceful: never raises.
    """
    if not isinstance(raw, str):
        raw = str(raw)
    original = raw
    out = raw.strip()
    out = "".join(c for c in out if ord(c) >= 32 or c in "\t\n\r")
    if len(out) > MAX_USER_INPUT_LENGTH:
        log_compliance(
            "input_sanitize",
            "intake",
            "User input truncated for length",
            validated=True,
            raw_value=original,
            sanitized_value=out[:MAX_USER_INPUT_LENGTH],
            metadata={"max_length": MAX_USER_INPUT_LENGTH},
        )
        out = out[:MAX_USER_INPUT_LENGTH]
    if out != original:
        log_compliance(
            "input_sanitize",
            "intake",
            "User input sanitized",
            validated=True,
            raw_value=original,
            sanitized_value=out,
        )
    return out


def validate_policy_number_format(value: str) -> Tuple[bool, str]:
    """
    Validate policy number format (alphanumeric, hyphens, underscores, spaces only).
    Returns (is_valid, sanitized_value). Graceful: returns (False, sanitized) on invalid.
    """
    sanitized = sanitize_user_input(value)
    if not sanitized:
        log_compliance("input_validation", "intake", "Empty policy number", validated=False, raw_value=value)
        return False, sanitized
    if not POLICY_NUMBER_PATTERN.match(sanitized):
        log_compliance(
            "input_validation",
            "intake",
            "Policy number contains disallowed characters",
            validated=False,
            raw_value=value,
            sanitized_value=sanitized,
        )
        safe = "".join(c for c in sanitized if c.isalnum() or c in "-_ ")
        return False, safe[:MAX_USER_INPUT_LENGTH]
    return True, sanitized


# --- Output filtering and content safety ---
def _filter_notice_unsafe_patterns(text: str) -> str:
    """Remove or replace obviously unsafe content (simple blocklist; extend or use Hub validator)."""
    if not text or not isinstance(text, str):
        return SAFE_NOTICE_FALLBACK
    out = text
    # Optional: blocklist of phrases to redact (compliance/safety)
    blocklist = []  # e.g. ["internal only", "confidential"]
    for phrase in blocklist:
        if phrase.lower() in out.lower():
            out = out.replace(phrase, "[REDACTED]")
    return out


def validate_notice_output(llm_notice_text: str) -> Tuple[str, bool]:
    """
    Validate and filter LLM-generated notice text: length, basic safety.
    Returns (filtered_text, success). On failure returns (SAFE_NOTICE_FALLBACK, False) and logs.
    Graceful: never raises.
    """
    try:
        if not llm_notice_text or not isinstance(llm_notice_text, str):
            log_compliance(
                "output_validation",
                "summary",
                "Notice text empty or invalid type; using fallback",
                validated=False,
                raw_value=str(llm_notice_text)[:100],
                sanitized_value=SAFE_NOTICE_FALLBACK,
            )
            return SAFE_NOTICE_FALLBACK, False
        text = llm_notice_text.strip()
        if len(text) > MAX_NOTICE_TEXT_LENGTH:
            log_compliance(
                "output_validation",
                "summary",
                "Notice text truncated for length",
                validated=True,
                raw_value=text[:200] + "...",
                sanitized_value=text[:MAX_NOTICE_TEXT_LENGTH],
                metadata={"max_length": MAX_NOTICE_TEXT_LENGTH},
            )
            text = text[:MAX_NOTICE_TEXT_LENGTH]
        text = _filter_notice_unsafe_patterns(text)
        log_compliance("output_validation", "summary", "Notice text validated", validated=True)
        return text, True
    except Exception as e:
        log_compliance(
            "output_validation",
            "summary",
            "Notice validation failed; using fallback",
            validated=False,
            error=str(e),
            raw_value=str(llm_notice_text)[:200] if llm_notice_text else None,
            sanitized_value=SAFE_NOTICE_FALLBACK,
        )
        return SAFE_NOTICE_FALLBACK, False


# --- Optional: Guardrails AI Guard (when Hub validators are installed) ---
_input_guard: Optional[Any] = None
_output_guard: Optional[Any] = None


def _create_input_guard() -> Optional[Any]:
    """Create Guard for input validation (prompt/user input). Use Hub validators if installed."""
    try:
        from guardrails import Guard, OnFailAction
        guard = Guard()
        # Example: guard.use(SomeHubValidator, on="prompt", on_fail=OnFailAction.NOOP)
        return guard
    except Exception:
        return None


def _create_output_guard() -> Optional[Any]:
    """Create Guard for output validation (LLM notice). Use Hub validators if installed."""
    try:
        from guardrails import Guard, OnFailAction
        guard = Guard()
        # Example: guard.use(ToxicLanguage, on="output", on_fail=OnFailAction.FIX)
        return guard
    except Exception:
        return None


def validate_input_with_guard(raw_input: str) -> Tuple[str, bool]:
    """
    Run optional Guardrails Guard on input. If no guard or validation fails, fall back to sanitize_user_input.
    Returns (sanitized_or_validated_input, success).
    """
    global _input_guard
    if _input_guard is None:
        _input_guard = _create_input_guard()
    if _input_guard is None or not _input_guard.validators:
        sanitized = sanitize_user_input(raw_input)
        return sanitized, True
    try:
        outcome = _input_guard.validate(raw_input)
        if outcome and getattr(outcome, "validated_output", None) is not None:
            return str(outcome.validated_output), True
    except Exception as e:
        log_compliance(
            "input_validation",
            "intake",
            "Guard input validation failed; using sanitizer",
            validated=False,
            error=str(e),
            raw_value=raw_input[:200],
        )
    return sanitize_user_input(raw_input), True


def validate_output_with_guard(llm_output: str) -> Tuple[str, bool]:
    """
    Run optional Guardrails Guard on LLM output. If no guard or failure, use validate_notice_output.
    Returns (filtered_text, success).
    """
    global _output_guard
    if _output_guard is None:
        _output_guard = _create_output_guard()
    if _output_guard is None or not _output_guard.validators:
        return validate_notice_output(llm_output)
    try:
        outcome = _output_guard.validate(llm_output)
        if outcome and getattr(outcome, "validated_output", None) is not None:
            text = str(outcome.validated_output)
            return validate_notice_output(text)
    except Exception as e:
        log_compliance(
            "output_validation",
            "summary",
            "Guard output validation failed; using filter",
            validated=False,
            error=str(e),
            raw_value=llm_output[:200] if llm_output else None,
        )
    return validate_notice_output(llm_output)


# --- Demo when run as script ---
if __name__ == "__main__":
    print("=== Guardrails safety demo ===\n")

    # 1. Input sanitization
    raw = "  POL-12345  \n\t "
    sanitized = sanitize_user_input(raw)
    print(f"1. sanitize_user_input({raw!r}) -> {sanitized!r}")

    # 2. Policy number validation
    for val in ["POL01234", "POL@#$bad", ""]:
        ok, out = validate_policy_number_format(val)
        print(f"2. validate_policy_number_format({val!r}) -> valid={ok}, out={out!r}")

    # 3. Notice output validation
    short_notice = "Your policy has been cancelled. Refund processed."
    long_notice = "X" * (MAX_NOTICE_TEXT_LENGTH + 100)
    for text in [short_notice, long_notice, ""]:
        filtered, success = validate_notice_output(text)
        print(f"3. validate_notice_output(...) -> success={success}, len={len(filtered)}")
        if len(filtered) <= 80:
            print(f"   text: {filtered!r}")

    print(f"\nCompliance log written to: {COMPLIANCE_LOG_PATH}")
    print("Done.")
