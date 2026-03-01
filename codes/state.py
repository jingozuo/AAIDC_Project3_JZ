"""
Graph state definitions — single source of truth for workflow state shape.

This module defines the state passed between all nodes in the insurance
cancellation LangGraph. All nodes read from and write to this state; no
other shared state should be used. Keys and types here must match what
nodes and tools expect (see agent_roles.py for which nodes read/write which keys).

Roles of types:
  - Phase: Controls routing; graph routers (graph.py) branch on phase values.
  - PolicyDetails: Canonical policy record; populated by intake (from data_lookup),
    extended by refund node (refund_amount, refund_reason).
  - InsuranceCancellationState: Full graph state; total=False means all keys optional
    for initial state; nodes add/update only the keys they are responsible for.
"""
from typing import Dict, List, Literal, Optional, TypedDict
from langgraph.graph.message import AnyMessage, add_messages
from langchain_core.messages import HumanMessage, SystemMessage
from typing_extensions import Annotated
from codes.prompt_builder import build_prompt_from_config

# All possible workflow phases. Routing in graph.py uses these to decide next node.
Phase = Literal[
    "ask_policy",              # Intake: ask user for policy number
    "awaiting_policy",         # Intake: looking up policy in CSV
    "confirm_customer",        # Intake: user confirming policy details
    "ready_for_analysis",      # After intake confirmation → analysis
    "human_eligibility_check", # After analysis (eligible) → HITL
    "ready_for_refund",        # After eligibility HITL approval → refund
    "human_refund_check",      # After refund calc → HITL
    "ready_for_summary",       # After refund HITL approval → log then summary
    "summary_complete",        # After notice generated
    "end"                      # Terminal (error, reject, or max attempts)
]

class PolicyDetails(TypedDict):
    """Canonical policy record; keys match CSV + fields added by refund node."""
    first_name: str
    last_name: str
    email: str
    policy_number: str
    policy_status: str
    start_date: str
    end_date: str
    payment_amount: str
    is_payment_made: bool
    is_policy_found: bool
    is_refund_eligible: bool
    is_refund_approved: bool = False
    refund_amount: Optional[float]   # Set by refund node
    refund_reason: Optional[str]      # Set by refund node


class InsuranceCancellationState(TypedDict, total=False):
    """
    State for the insurance cancellation graph. All nodes read/write subsets of these keys.
    See agent_roles.py for which agent reads which inputs and writes which outputs.
    """

    phase: Phase
    policy_details: PolicyDetails
    user_input: str
    # Set by runner (CLI/Streamlit) when resuming after intake interrupt; intake node clears after use
    pending_user_input: Optional[str]
    messages: Annotated[list[AnyMessage], add_messages]
    output: str
    invalid_policy_attempts: int

    # HITL: set by main.py after human review, read by HITL nodes to decide next phase
    human_decision: Optional[Literal["approve", "reject"]]
    human_decision_reason: Optional[str]
    hitl_checkpoint: Optional[str]
