"""
Refund Calculator — single-responsibility tool for refund computation.

Role: Compute refund amount from policy dates and payment only. No I/O, no logging.
Used by: Refund agent node only (see agent_roles.TOOL_RESPONSIBILITIES). All refund
math lives here for clarity and testability.

Input contract (policy_details):
  - start_date, end_date: str in DATE_FORMAT ("YYYY-MM-DD")
  - payment_amount: number or string coercible to float (e.g. from CSV as "600")
Output: (success: bool, reason: str, amount: float). When success is False, amount is 0.0.

Algorithm: Refund = payment * (remaining_days / total_days); total_days = end - start,
remaining_days = end - today. Rounded to 2 decimals.
Edge cases: invalid dates → "Invalid date format"; expired → no refund; not started → no refund;
invalid payment → "Invalid payment amount".
"""
from datetime import datetime
from typing import Dict, Any, Tuple

# Expected date format for start_date and end_date in policy_details (e.g. "2024-01-15").
DATE_FORMAT = "%Y-%m-%d"


def calculate_refund_amount(policy_details: Dict[str, Any]) -> Tuple[bool, str, float]:
    """
    Calculate the refund amount for the policy (proportional to remaining days).

    Used only by the Refund agent. Pure function: no I/O, no side effects.

    Args:
        policy_details: Dict with start_date, end_date (YYYY-MM-DD), payment_amount (float or str).

    Returns:
        (success, reason, refund_amount). success False implies refund_amount 0.0; reason explains why.
    """

    try:
        start_date_str = policy_details.get("start_date", "") or ""
        start_date = datetime.strptime(start_date_str, DATE_FORMAT)
        end_date_str = policy_details.get("end_date", "") or ""
        end_date = datetime.strptime(end_date_str, DATE_FORMAT)
        current_date = datetime.now()
    except ValueError:
        return False, "Invalid date format", 0.0

    if current_date >= end_date:
        return False, "Policy has already expired. No refund available.", 0.0

    if current_date < start_date:
        return False, "Policy has not started yet. No refund available.", 0.0

    total_days = (end_date - start_date).days
    remaining_days = (end_date - current_date).days
    refund_percentage = (remaining_days / total_days) * 100
    # payment_amount from CSV is a string (e.g. "600"); convert to float for calculation
    payment_amount_raw = policy_details.get("payment_amount", 0) or 0
    try:
        payment_amount = float(payment_amount_raw)
    except (TypeError, ValueError):
        return False, "Invalid payment amount", 0.0
    refund_amount = payment_amount * refund_percentage / 100

    return True, "Refund amount calculated successfully.", round(refund_amount, 2)
