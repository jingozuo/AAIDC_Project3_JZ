"""
Human-in-the-loop CLI — collect approve/reject from the user when the graph interrupts.

Role: When a HITL node returns interrupt(...), main passes the interrupt payload here.
This function prints instructions, policy summary, policy details, and prompts for [A]pprove
or [R]eject. Returns a dict with human_decision ("approved" | "rejected"), human_notes,
and hitl_checkpoint (so main can update_state and resume). Non-interactive: set
HITL_CHOICE=a|r or use --approve/--reject (main passes as default_choice).
"""
import os
import sys
from typing import Dict, Any, Optional
from pprint import pprint


def run_human_review(interrupt_payload: Dict[str, Any], default_choice: Optional[str] = None) -> Dict[str, Any]:
    """
    Run the human review CLI: show summary and policy details, then ask Approve or Reject.

    Args:
        interrupt_payload: Dict from graph interrupt (keys: payload, instructions, messages).
        default_choice: Optional "a" or "r" for non-interactive mode (e.g. from argv or HITL_CHOICE).

    Returns:
        Dict with human_decision ("approved" | "rejected"), human_notes, hitl_checkpoint (str).
    """
    if not isinstance(interrupt_payload, dict):
        interrupt_payload = {}

    payload = interrupt_payload.get("payload", {}) or {}
    instructions = interrupt_payload.get("instructions", "")

    print(instructions)
    print(f"\nStep: {payload.get('checkpoint_name', '')}")
    policy_number = payload.get("policy_number") or (payload.get("policy_details") or {}).get("policy_number", "")
    print(f"Policy Number: {policy_number}")

    print("\n--- SYSTEM SUMMARY ---")
    print(payload.get("output", payload.get("summary", "No summary provided")))

    print("\n--- POLICY DETAILS ---")
    pprint(payload.get("policy_details", {}))

    print("\nActions:")
    print("  [A] Approve")
    print("  [R] Reject")

    user_choice = input("Your choice (A/R): ").strip().lower()

    if not user_choice:
        user_choice = default_choice
    elif user_choice not in ("a", "r"):
        print("Invalid choice. Please enter A or R.")
        return run_human_review(interrupt_payload, default_choice)

    response = {
        "human_decision": None,
        "human_notes": None,
        "hitl_checkpoint": None,
    }

    if user_choice == "a":
        response["human_decision"] = "approved"
        response["human_notes"] = "Approved by human reviewer"
        response["hitl_checkpoint"] = payload.get('checkpoint_name')
        print(f"User choose to approve {payload.get('checkpoint_name')}.\nMoving to the next phase...")
    else:
        response["human_decision"] = "rejected"
        response["human_notes"] = "Rejected by human reviewer"
        response["hitl_checkpoint"] = payload.get('checkpoint_name')
        print(f"User choose to reject {payload.get('checkpoint_name')}.\nStopping the workflow...")

    print("\n🧑 Human Review Submitted")
    return response
