"""Unit tests for the cancellation_rules tool (eligibility checks)."""
from datetime import datetime, timedelta
import pytest

from codes.tools.cancellation_rules import (
    check_cancellation_eligibility,
    DATE_FORMAT,
)


class TestCheckCancellationEligibility:
    """Test check_cancellation_eligibility rules: active, payment made, end_date valid."""

    def test_eligible_active_paid_future_end_returns_true(self):
        end = datetime.now() + timedelta(days=30)
        policy = {
            "policy_status": "active",
            "is_payment_made": True,
            "end_date": end.strftime(DATE_FORMAT),
        }
        is_eligible, reason = check_cancellation_eligibility(policy)
        assert is_eligible is True
        assert "eligible" in reason.lower()

    def test_not_active_returns_false(self):
        end = datetime.now() + timedelta(days=30)
        policy = {
            "policy_status": "Cancelled",
            "is_payment_made": True,
            "end_date": end.strftime(DATE_FORMAT),
        }
        is_eligible, reason = check_cancellation_eligibility(policy)
        assert is_eligible is False
        assert "not active" in reason.lower()

    def test_status_case_insensitive_active(self):
        end = datetime.now() + timedelta(days=30)
        policy = {
            "policy_status": "ACTIVE",
            "is_payment_made": True,
            "end_date": end.strftime(DATE_FORMAT),
        }
        is_eligible, _ = check_cancellation_eligibility(policy)
        assert is_eligible is True

    def test_payment_not_made_returns_false(self):
        end = datetime.now() + timedelta(days=30)
        policy = {
            "policy_status": "active",
            "is_payment_made": False,
            "end_date": end.strftime(DATE_FORMAT),
        }
        is_eligible, reason = check_cancellation_eligibility(policy)
        assert is_eligible is False
        assert "payment" in reason.lower()

    def test_payment_made_string_true_accepted(self):
        end = datetime.now() + timedelta(days=30)
        policy = {
            "policy_status": "active",
            "is_payment_made": "true",
            "end_date": end.strftime(DATE_FORMAT),
        }
        is_eligible, _ = check_cancellation_eligibility(policy)
        assert is_eligible is True

    def test_missing_end_date_returns_false(self):
        policy = {
            "policy_status": "active",
            "is_payment_made": True,
            "end_date": "",
        }
        is_eligible, reason = check_cancellation_eligibility(policy)
        assert is_eligible is False
        assert "end date" in reason.lower() or "date" in reason.lower()

    def test_invalid_date_format_returns_false(self):
        policy = {
            "policy_status": "active",
            "is_payment_made": True,
            "end_date": "31/12/2025",
        }
        is_eligible, reason = check_cancellation_eligibility(policy)
        assert is_eligible is False
        assert "invalid" in reason.lower() or "format" in reason.lower()

    def test_expired_policy_returns_false(self):
        past = datetime.now() - timedelta(days=10)
        policy = {
            "policy_status": "active",
            "is_payment_made": True,
            "end_date": past.strftime(DATE_FORMAT),
        }
        is_eligible, reason = check_cancellation_eligibility(policy)
        assert is_eligible is False
        assert "expired" in reason.lower()
