"""Unit tests for the refund_calculator tool (refund amount computation)."""
from datetime import datetime, timedelta
import pytest

from codes.tools.refund_calculator import calculate_refund_amount, DATE_FORMAT


class TestCalculateRefundAmount:
    """Test calculate_refund_amount: proportional refund by remaining days."""

    def _policy(self, start_delta_days: int, end_delta_days: int, payment: float = 600.0):
        start = datetime.now() + timedelta(days=start_delta_days)
        end = datetime.now() + timedelta(days=end_delta_days)
        return {
            "start_date": start.strftime(DATE_FORMAT),
            "end_date": end.strftime(DATE_FORMAT),
            "payment_amount": payment,
        }

    def test_success_returns_true_reason_and_positive_amount(self):
        policy = self._policy(-30, 60, 600.0)
        success, reason, amount = calculate_refund_amount(policy)
        assert success is True
        assert "calculated" in reason.lower() or "success" in reason.lower()
        assert amount >= 0
        assert isinstance(amount, float)

    def test_refund_proportional_to_remaining_days(self):
        policy = self._policy(-10, 90, 1000.0)
        success, _, amount = calculate_refund_amount(policy)
        assert success is True
        assert 800 <= amount <= 1000

    def test_payment_amount_string_coerced_to_float(self):
        policy = self._policy(-30, 60, 600.0)
        policy["payment_amount"] = "600"
        success, _, amount = calculate_refund_amount(policy)
        assert success is True
        assert amount > 0

    def test_expired_policy_returns_false_zero_refund(self):
        policy = self._policy(-60, -10, 600.0)
        success, reason, amount = calculate_refund_amount(policy)
        assert success is False
        assert amount == 0.0
        assert "expired" in reason.lower()

    def test_policy_not_started_returns_false(self):
        policy = self._policy(10, 70, 600.0)
        success, reason, amount = calculate_refund_amount(policy)
        assert success is False
        assert amount == 0.0
        assert "not started" in reason.lower()

    def test_invalid_date_format_returns_false(self):
        policy = {
            "start_date": "01/15/2025",
            "end_date": "2025-12-31",
            "payment_amount": 600,
        }
        success, reason, amount = calculate_refund_amount(policy)
        assert success is False
        assert amount == 0.0
        assert "invalid" in reason.lower() or "format" in reason.lower()

    def test_invalid_payment_amount_returns_false(self):
        policy = self._policy(-30, 60, 600.0)
        policy["payment_amount"] = "not_a_number"
        success, reason, amount = calculate_refund_amount(policy)
        assert success is False
        assert amount == 0.0
        assert "payment" in reason.lower()

    def test_refund_rounded_to_two_decimals(self):
        policy = self._policy(-1, 100, 100.0)
        success, _, amount = calculate_refund_amount(policy)
        assert success is True
        assert amount == round(amount, 2)
