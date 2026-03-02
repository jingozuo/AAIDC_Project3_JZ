"""
Agent and tool role definitions — single source of truth for responsibilities.

This module defines:
  1. AGENT_ROLES: Each graph node (agent) — id, name, responsibility, inputs from state,
     outputs written to state, and tools_used. Use for documentation and to avoid
     overlap (e.g. only Refund agent uses refund_calculator; only Intake uses data_lookup).
  2. TOOL_RESPONSIBILITIES: Each tool — id, name, responsibility, used_by (agent ids).
  3. get_agent_role(agent_id), get_tool_responsibility(tool_id): Lookup by id.

When adding a new node or tool: add an entry here and document inputs/outputs or used_by.
"""

from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Graph nodes (agents): id must match graph.add_node key; inputs/outputs are state keys
# ---------------------------------------------------------------------------

AGENT_ROLES: List[Dict[str, Any]] = [
    {
        "id": "intake",
        "name": "Intake Agent",
        "responsibility": "Collect policy number, look up policy in data source, confirm with user. Loops until policy found and confirmed or max attempts.",
        "inputs": ["user_input", "phase", "invalid_policy_attempts"],
        "outputs": ["policy_details", "phase", "messages", "output"],
        "tools_used": ["data_lookup"],
    },
    {
        "id": "analysis",
        "name": "Analysis Agent",
        "responsibility": "Determine if the policy is eligible for cancellation (status, payment, dates). No refund calculation.",
        "inputs": ["policy_details", "phase"],
        "outputs": ["phase", "messages", "output"],
        "tools_used": ["cancellation_rules"],
    },
    {
        "id": "eligibility_hitl",
        "name": "Eligibility HITL",
        "responsibility": "Human approval checkpoint after eligibility. Approve → refund; Reject → end.",
        "inputs": ["policy_details", "output", "human_decision", "hitl_checkpoint"],
        "outputs": ["phase"],
        "tools_used": [],
    },
    {
        "id": "refund",
        "name": "Refund Agent",
        "responsibility": "Compute refund amount from policy (dates, payment). Does not log; hands off to human review.",
        "inputs": ["policy_details", "phase"],
        "outputs": ["policy_details", "phase", "messages", "output"],
        "tools_used": ["cancellation_rules", "refund_calculator"],
    },
    {
        "id": "refund_hitl",
        "name": "Refund HITL",
        "responsibility": "Human approval checkpoint after refund calculation. Approve → logger; Reject → end.",
        "inputs": ["policy_details", "output", "human_decision", "hitl_checkpoint"],
        "outputs": ["phase"],
        "tools_used": [],
    },
    {
        "id": "logger",
        "name": "Logger Agent",
        "responsibility": "Persist refund record to CSV only after human approval. No other side effects.",
        "inputs": ["policy_details"],
        "outputs": [],
        "tools_used": ["refund_logger"],
    },
    {
        "id": "summary",
        "name": "Summary Agent",
        "responsibility": "Generate cancellation notice text and PDF from policy and refund details.",
        "inputs": ["policy_details", "phase"],
        "outputs": ["phase", "messages", "output", "pdf_path"],
        "tools_used": ["notice_generator"],
    },
]

# ---------------------------------------------------------------------------
# Tools: id must match the function used in nodes (e.g. data_lookup → lookup_policy_in_csv).
# Paths (DATA_FILE_PATH, OUTPUTS_DIR) are in paths.py.
# ---------------------------------------------------------------------------

TOOL_RESPONSIBILITIES: List[Dict[str, Any]] = [
    {
        "id": "data_lookup",
        "name": "Data Lookup",
        "responsibility": "Look up policy by number in CSV. Used only by Intake. Path: paths.DATA_FILE_PATH.",
        "used_by": ["intake"],
    },
    {
        "id": "cancellation_rules",
        "name": "Cancellation Rules",
        "responsibility": "Evaluate eligibility (active status, payment made, dates). Used by Analysis and Refund.",
        "used_by": ["analysis", "refund"],
    },
    {
        "id": "refund_calculator",
        "name": "Refund Calculator",
        "responsibility": "Compute refund amount from policy dates and payment. Used only by Refund agent. No I/O.",
        "used_by": ["refund"],
    },
    {
        "id": "refund_logger",
        "name": "Refund Logger",
        "responsibility": "Append approved refund records to CSV. Used only by Log Refund node. Path: paths.OUTPUTS_DIR.",
        "used_by": ["logger"],
    },
    {
        "id": "notice_generator",
        "name": "Notice Generator",
        "responsibility": "Generate PDF cancellation notice. Used only by Summary. Path: paths.OUTPUTS_DIR.",
        "used_by": ["summary"],
    },
]


def get_agent_role(agent_id: str) -> Optional[Dict[str, Any]]:
    """
    Return the role definition for a graph node by id.

    Args:
        agent_id: Node id as used in graph (e.g. "intake", "refund", "eligibility_hitl").

    Returns:
        Dict with keys id, name, responsibility, inputs, outputs, tools_used; or None if not found.
    """
    for r in AGENT_ROLES:
        if r["id"] == agent_id:
            return r
    return None


def get_tool_responsibility(tool_id: str) -> Optional[Dict[str, Any]]:
    """
    Return the responsibility definition for a tool by id.

    Args:
        tool_id: Tool id as in TOOL_RESPONSIBILITIES (e.g. "data_lookup", "refund_calculator").

    Returns:
        Dict with keys id, name, responsibility, used_by; or None if not found.
    """
    for t in TOOL_RESPONSIBILITIES:
        if t["id"] == tool_id:
            return t
    return None
