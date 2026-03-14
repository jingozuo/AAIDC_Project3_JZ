"""
Data Lookup — single-responsibility tool for policy lookup by policy number.

Role: Read from the canonical policies CSV (paths.DATA_FILE_PATH) and return one
record as a dict with space-separated keys (First Name, Policy Number, etc.). Used
only by the Intake agent (see agent_roles.TOOL_RESPONSIBILITIES). No other module
should read the policies CSV directly; use this tool for a single source of truth.

Performance: CSV is loaded once per process into an in-memory cache; lookups use
the cache to avoid repeated disk I/O.
"""
import csv
from typing import Optional, Dict, Any, List

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

# In-memory cache: (file_path, list of normalized row dicts). Cleared when path changes.
_policy_cache: Optional[List[Dict[str, Any]]] = None
_policy_cache_path: Optional[str] = None


def _load_policy_cache(csv_path: str = DATA_FILE_PATH) -> List[Dict[str, Any]]:
    """Load CSV into list of dicts with normalized keys. Reuses cache if path unchanged."""
    global _policy_cache, _policy_cache_path
    if _policy_cache is not None and _policy_cache_path == csv_path:
        return _policy_cache
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append({CSV_KEY_MAP.get(k, k): v.strip() if isinstance(v, str) else v for k, v in row.items()})
    _policy_cache_path = csv_path
    _policy_cache = rows
    return _policy_cache


def lookup_policy_in_csv(policy_number: str, csv_path: str = DATA_FILE_PATH) -> Optional[Dict[str, Any]]:
    """
    Look up a policy in the CSV by policy number (exact match, case-sensitive as stored).

    Uses an in-memory cache of the CSV for the process; first call loads the file,
    subsequent lookups (and retries) use the cache.

    Args:
        policy_number: Policy number to search for (caller may normalize e.g. .strip().upper()).
        csv_path: Path to CSV (default: DATA_FILE_PATH). Changing it clears the cache for next load.

    Returns:
        Dict with keys "First Name", "Last Name", "Email", "Policy Number", "Policy Status",
        "Start Date", "End Date", "Payment Amount", "Is Payment Made"; or None if not found.
    """
    try:
        rows = _load_policy_cache(csv_path)
    except OSError:
        return None
    key = "Policy Number"  # normalized key after CSV_KEY_MAP
    for row in rows:
        if (row.get(key) or "").strip() == policy_number:
            return dict(row)
    return None