"""
Data Lookup — single-responsibility tool for policy lookup by policy number.

Role: Read from the canonical policies CSV (paths.DATA_FILE_PATH) and return one
record as a dict with space-separated keys (First Name, Policy Number, etc.). Used
only by the Intake agent (see agent_roles.TOOL_RESPONSIBILITIES). No other module
should read the policies CSV directly; use this tool for a single source of truth.
"""
import csv
from typing import Optional, Dict, Any

from codes.paths import DATA_FILE_PATH

# Map CSV column names (underscores) to keys expected by nodes (spaces).
CSV_KEY_MAP = {
    "Policy_Number": "Policy Number",
    "First_Name": "First Name",
    "Last_Name": "Last Name",
    "Email": "Email",
    "Start_Date": "Start Date",
    "End_Date": "End Date",
    "Policy_Status": "Policy Status",
    "Payment_Amount": "Payment Amount",
    "Is_Payment_Paid": "Is Payment Made",
}


def lookup_policy_in_csv(policy_number: str) -> Optional[Dict[str, Any]]:
    """
    Look up a policy in the CSV by policy number (exact match, case-sensitive as stored).

    Args:
        policy_number: Policy number to search for (caller may normalize e.g. .strip().upper()).

    Returns:
        Dict with keys "First Name", "Last Name", "Email", "Policy Number", "Policy Status",
        "Start Date", "End Date", "Payment Amount", "Is Payment Made"; or None if not found.
    """
    with open(DATA_FILE_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("Policy_Number", "").strip() == policy_number:
                return {CSV_KEY_MAP.get(k, k): v.strip() if isinstance(v, str) else v for k, v in row.items()}
    return None