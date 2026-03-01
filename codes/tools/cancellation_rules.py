"""
Cancellation Rules — single-responsibility tool for eligibility checks.

Role: Evaluate whether a policy is eligible for cancellation (status, payment, dates).
No refund calculation; used by Analysis and Refund agents only (see agent_roles.TOOL_RESPONSIBILITIES).

Rules (all must pass):
  1. policy_status must be "active" (case-insensitive).
  2. is_payment_made must be truthy (True, "true", "yes", "1").
  3. end_date must be present, parseable as DATE_FORMAT, and current date <= end_date.

Input: policy_details dict with policy_status, is_payment_made, end_date.
Output: (eligible: bool, reason: str).
"""
from datetime import datetime
from typing import Dict, Any, Tuple

# Date format for end_date (e.g. "2024-12-31").
DATE_FORMAT = "%Y-%m-%d"


def check_cancellation_eligibility(policy_details: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Check whether the policy satisfies all cancellation eligibility rules.

    Args:
        policy_details: Dict with policy_status, is_payment_made, end_date (str in YYYY-MM-DD).

    Returns:
        (True, "Policy is eligible for cancellation") or (False, reason) e.g. "Policy is not active".
    """

    status = policy_details.get("policy_status", "").lower()
    payment_made = policy_details.get("is_payment_made", False)

    #Rule 1: Status must be Active
    if policy_details.get("policy_status", "").lower() != "active":
        return False, "Policy is not active"

    #Rule 2: Payment must be made
    payment_made = str(policy_details.get("is_payment_made", False)).lower() in ("true", "yes", "1")
    if not payment_made:
        return False, "Payment has not been made"

    #Rule 3: Current date must be before the end date of the policy (end_date from CSV is a string)
    try:
        end_date_str = policy_details.get("end_date", "") or ""
        if not end_date_str:
            return False, "Missing policy end date"
        end_date = datetime.strptime(str(end_date_str).strip(), DATE_FORMAT)
        current_date = datetime.now()
    except ValueError:
        return False, "Invalid date format"

    if current_date > end_date:
        return False, "Policy has already expired"
    
    return True, "Policy is eligible for cancellation"