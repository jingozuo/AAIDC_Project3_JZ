"""Unit tests for guardrails_safety: input validation, output filtering, compliance logging."""
import json
import os
import pytest

from codes.guardrails_safety import (
    sanitize_user_input,
    validate_policy_number_format,
    validate_notice_output,
    validate_output_with_guard,
    log_compliance,
    SAFE_NOTICE_FALLBACK,
    MAX_USER_INPUT_LENGTH,
    MAX_NOTICE_TEXT_LENGTH,
)


class TestSanitizeUserInput:
    def test_strips_whitespace(self):
        assert sanitize_user_input("  POL01212  ") == "POL01212"

    def test_truncates_long_input(self):
        long_str = "A" * (MAX_USER_INPUT_LENGTH + 100)
        out = sanitize_user_input(long_str)
        assert len(out) == MAX_USER_INPUT_LENGTH

    def test_removes_control_chars(self):
        out = sanitize_user_input("POL\x0012\x0b12")
        assert "\x00" not in out and "\x0b" not in out

    def test_non_string_coerced(self):
        assert sanitize_user_input(123) == "123"


class TestValidatePolicyNumberFormat:
    def test_valid_alphanumeric(self):
        valid, out = validate_policy_number_format("POL01212")
        assert valid is True
        assert out == "POL01212"

    def test_valid_with_hyphen(self):
        valid, out = validate_policy_number_format("POL-01212")
        assert valid is True

    def test_empty_invalid(self):
        valid, out = validate_policy_number_format("")
        assert valid is False

    def test_sanitizes_strip(self):
        _, out = validate_policy_number_format("  POL01212  ")
        assert out == "POL01212"


class TestValidateNoticeOutput:
    def test_valid_text_returned(self):
        text, ok = validate_notice_output("Your policy has been cancelled. Refund processed.")
        assert ok is True
        assert "cancelled" in text

    def test_empty_returns_fallback(self):
        text, ok = validate_notice_output("")
        assert ok is False
        assert text == SAFE_NOTICE_FALLBACK

    def test_none_returns_fallback(self):
        text, ok = validate_notice_output(None)
        assert ok is False
        assert text == SAFE_NOTICE_FALLBACK

    def test_truncates_very_long(self):
        long_str = "A" * (MAX_NOTICE_TEXT_LENGTH + 500)
        text, ok = validate_notice_output(long_str)
        assert ok is True
        assert len(text) == MAX_NOTICE_TEXT_LENGTH

    def test_graceful_on_exception(self):
        text, ok = validate_notice_output(object())
        assert ok is False
        assert text == SAFE_NOTICE_FALLBACK


class TestValidateOutputWithGuard:
    def test_returns_filtered_text_without_guard(self):
        text, ok = validate_output_with_guard("Cancellation notice content.")
        assert ok is True
        assert "Cancellation" in text or text == "Cancellation notice content."


class TestLogCompliance:
    def test_log_creates_file(self, tmp_path, monkeypatch):
        import codes.guardrails_safety as mod
        log_path = os.path.join(str(tmp_path), "compliance.jsonl")
        monkeypatch.setattr(mod, "LOGS_DIR", str(tmp_path))
        monkeypatch.setattr(mod, "COMPLIANCE_LOG_PATH", log_path)
        log_compliance("test", "test_stage", "Test message", validated=True)
        assert os.path.isfile(log_path)
        with open(log_path, encoding="utf-8") as f:
            line = f.readline()
        entry = json.loads(line)
        assert entry["event_type"] == "test"
        assert entry["stage"] == "test_stage"
        assert entry["message"] == "Test message"
        assert entry["validated"] is True
