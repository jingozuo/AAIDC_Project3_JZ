"""
Refund Logger — single-responsibility tool for persisting approved refund records.

Role: Append one refund record to a CSV in paths.OUTPUTS_DIR (refund_log.csv). Used
only by the Log Refund node after human approval (see agent_roles.TOOL_RESPONSIBILITIES).
Creates OUTPUTS_DIR and file if missing; assigns Refund_record_id automatically.
"""
import csv
import os
from datetime import datetime
from typing import Dict, Any

from codes.paths import OUTPUTS_DIR

REFUND_LOG_FILE_PATH = os.path.join(OUTPUTS_DIR, "refund_log.csv")

# Column headers for refund_log.csv; must match keys in the row dict written below.
HEADERS = [
    "Refund_record_id",
    "Request_date",
    "Policy_number",
    "First_name",
    "Last_name",
    "Email",
    "Refund_amount",
    "Refund_reason"
]


def log_refund_record(policy_details: Dict[str, Any], refund_amount: float, refund_reason: str) -> bool:
    """
    Append one refund record to refund_log.csv. Creates OUTPUTS_DIR and file if needed.

    Args:
        policy_details: Dict with policy_number, first_name, last_name, email (snake_case).
        refund_amount: Refund amount (float).
        refund_reason: Human-readable reason string.

    Returns:
        True on success. Prints confirmation message.
    """
    os.makedirs(OUTPUTS_DIR, exist_ok=True)

    file_path = os.path.join(OUTPUTS_DIR, "refund_log.csv")
    file_exists = os.path.isfile(file_path)

    refund_record_id = get_next_refund_record_id()
    row = {
        "Refund_record_id": refund_record_id,
        "Request_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Policy_number": policy_details.get("policy_number", ""),
        "First_name": policy_details.get("first_name", ""),
        "Last_name": policy_details.get("last_name", ""),
        "Email": policy_details.get("email", ""),
        "Refund_amount": refund_amount,
        "Refund_reason": refund_reason,
    }

    with open(file_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
    print(f"✅ Refund record logged successfully: {refund_record_id}")
    return True

def get_next_refund_record_id() -> int:
    """
    Return the next sequential Refund_record_id (1 if file missing, else count + 1).
    """
    if not os.path.isfile(REFUND_LOG_FILE_PATH):
        return 1
    with open(REFUND_LOG_FILE_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return len(list(reader)) + 1