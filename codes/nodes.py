"""
Graph nodes — one callable per agent/node in the insurance cancellation workflow.

Each make_*_agent_node or make_*_node returns a function (state) -> state_updates
that the graph invokes. Nodes read from InsuranceCancellationState and return
a dict of keys to merge into state (see agent_roles.py for inputs/outputs per node).

Roles:
  - Intake: collect policy number, lookup via data_lookup, confirm with user; loops until confirmed or max attempts.
  - Analysis: check eligibility via cancellation_rules; sets phase to human_eligibility_check or end.
  - eligibility_hitl / refund_hitl: interrupt for human review; on resume, set phase from human_decision.
  - Refund: cancellation_rules + refund_calculator; writes refund_amount/refund_reason to policy_details.
  - Logger: persist refund to CSV via refund_logger (after HITL approval).
  - Summary: generate notice text (LLM) and PDF via notice_generator.
"""
from typing import Any, Callable, Dict, Literal
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt
from codes.state import InsuranceCancellationState
from codes.llm import get_llm
from codes.prompt_builder import build_prompt_from_config
from codes.tools.data_lookup import lookup_policy_in_csv
from codes.tools.cancellation_rules import check_cancellation_eligibility
from codes.tools.refund_calculator import calculate_refund_amount
from codes.tools.refund_logger import log_refund_record
from codes.tools.notice_generator import generate_notice_pdf
from codes.guardrails_safety import (
    sanitize_user_input,
    validate_policy_number_format,
    validate_output_with_guard,
    log_compliance,
    SAFE_NOTICE_FALLBACK,
)
from codes.retry_logging import call_with_retry

# Max times the user can enter an invalid policy number before workflow ends.
MAX_POLICY_LOOKUP_ATTEMPTS = 3


def make_intake_agent_node(llm_model: str, llm_intake_prompt_config: Dict[str, Any]) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    """
    Build the Intake agent node: collect policy number, look up policy (data_lookup), confirm with user.

    Phases: ask_policy → awaiting_policy → confirm_customer → ready_for_analysis (or end).
    Uses tools: data_lookup only. Outputs: policy_details, phase, messages, output, invalid_policy_attempts.
    """

    llm = llm_model

    def run_llm(messages):
        response = llm.invoke(messages)
        return response

    def intake_node(state: InsuranceCancellationState) -> Dict[str, Any]:
        print("\n")
        print("  → Intake node running (phase=%s)" % state.get("phase", "ask_policy"))
        phase = state.get("phase", "ask_policy")
        user_input = state.get("user_input", "")

        llm_intake_prompt = build_prompt_from_config(llm_intake_prompt_config, input_data=user_input)

        # Phase 1: Ask for policy number
        if phase == "ask_policy":
            # print(f"✅ Please provide your policy number: ")
            raw_input = (state.get("pending_user_input") or "").strip() or (state.get("user_input") or "").strip()
            if not raw_input:
                interrupt({"type": "intake", "input_kind": "policy_number", "message": "✅ Please provide your policy number:"})
                return {}
            user_input = sanitize_user_input(raw_input)
            is_valid_format, user_input = validate_policy_number_format(user_input)
            llm_intake_chat_messages = [
                SystemMessage(content=llm_intake_prompt),
                HumanMessage(content=f"Please provide your policy number.\n\n User Input: {user_input}"),
            ]
            output = f"Policy number received: {user_input}. Looking up full details..."
            print(f"✅ {output}")
            return {"phase": "awaiting_policy", "user_input": user_input, "pending_user_input": None, "messages": llm_intake_chat_messages, "output": output}

        # Phase 2: Look for policy number in CSV (with retry and logging)
        if phase == "awaiting_policy":
            print(f"✅ Looking for policy number in CSV")
            policy_number = user_input.strip().upper()
            try:
                record = call_with_retry(
                    lookup_policy_in_csv,
                    policy_number,
                    name="data_lookup",
                    stage="intake",
                    log_args_preview=policy_number,
                )
            except Exception:
                record = None
                log_compliance(
                    "tool_failure",
                    "intake",
                    "Policy lookup failed after retries (I/O or data error)",
                    metadata={"policy_number": policy_number},
                )

            if not record:
                attempts = state.get("invalid_policy_attempts", 0) + 1
                if attempts >= MAX_POLICY_LOOKUP_ATTEMPTS:
                    output = f"Maximum attempts ({MAX_POLICY_LOOKUP_ATTEMPTS}) reached. Please try again later."
                    print(f"✅ {output}")
                    llm_intake_chat_messages = HumanMessage(content=output)
                    return {"phase": "end", "invalid_policy_attempts": attempts, "messages": [llm_intake_chat_messages], "output": output}
                output = f"Policy number not found. Please provide a correct policy number. (Attempt {attempts}/{MAX_POLICY_LOOKUP_ATTEMPTS})"
                print(f"✅ {output}")
                raw_retry = (state.get("pending_user_input") or "").strip()
                if not raw_retry:
                    interrupt({"type": "intake", "input_kind": "retry_policy", "attempts": attempts})
                    return {}
                user_input = sanitize_user_input(raw_retry)
                _, user_input = validate_policy_number_format(user_input)
                llm_intake_chat_messages = HumanMessage(content=output)
                return {"phase": "awaiting_policy", "user_input": user_input, "pending_user_input": None, "invalid_policy_attempts": attempts, "messages": [llm_intake_chat_messages], "output": output}

            # Normalize boolean from CSV (TRUE/FALSE string)
            is_paid = record.get("Is Payment Made", "")
            if isinstance(is_paid, str):
                is_payment_made = is_paid.upper() in ("TRUE", "YES", "1")
            else:
                is_payment_made = bool(is_paid)

            policy_details = {
                "first_name": record["First Name"],
                "last_name": record["Last Name"],
                "email": record["Email"],
                "is_policy_found": True,
                "policy_number": record["Policy Number"],
                "policy_status": record["Policy Status"],
                "start_date": record["Start Date"],
                "end_date": record["End Date"],
                "payment_amount": record["Payment Amount"],
                "is_payment_made": is_payment_made,
            }

            llm_intake_chat_messages = [
                HumanMessage(
                    content=(
                        "I found the following policy details:\n\n"
                        f"First Name: {record['First Name']}\n"
                        f"Last Name: {record['Last Name']}\n"
                        f"Email: {record['Email']}\n"
                        f"Policy Number: {record['Policy Number']}\n"
                        f"Policy Status: {record['Policy Status']}\n"
                        f"Start Date: {record['Start Date']}\n"
                        f"End Date: {record['End Date']}\n"
                        f"Payment Amount: {record['Payment Amount']}\n"
                        f"Is this information correct? Please confirm with 'yes' or 'no'.\n\n User Input: {user_input}"
                    )
                )
            ]
            # Show full details from CSV, one per line; reset failed-attempt counter on success
            output_lines = [f"  {k}: {v}" for k, v in policy_details.items()]
            output = "\n".join(output_lines)
            print("✅ Results (policy details from record):")
            print(output)
            return {"phase": "confirm_customer", "policy_details": policy_details, "invalid_policy_attempts": 0, "messages": llm_intake_chat_messages, "output": output}

        # Phase 3: Confirm customer
        if phase == "confirm_customer":
            print(f"✅ Confirming customer")
            # print(f"✅ Please confirm if the information above is correct: [yes/no]")
            raw_confirm = (state.get("pending_user_input") or "").strip().lower()
            if not raw_confirm:
                interrupt({
                    "type": "intake",
                    "input_kind": "confirm",
                    "message": "✅ Please confirm if the information above is correct (yes/no):",
                    "policy_details": state.get("policy_details"),
                })
                return {}
            user_input = sanitize_user_input(raw_confirm.lower())
            if user_input in ("yes", "y"):
                output = (
                    f"Policy is confirmed.\n"
                    f"Moving to the next phase..."
                )
                print(f"✅ {output}")
                llm_intake_chat_messages = HumanMessage(content=output)
                return {"phase": "ready_for_analysis", "pending_user_input": None, "messages": [llm_intake_chat_messages], "output": output}

            if user_input in ("no", "n"):
                # Need correct policy number from next interrupt round (do not reuse pending_user_input here—it was "no")
                interrupt({
                    "type": "intake",
                    "input_kind": "correct_policy",
                    "message": "✅ Please enter the correct policy number:",
                })
                return {"pending_user_input": None}

            # raw_confirm is the new policy number (resumed after correct_policy interrupt)
            if user_input.lower() in ("quit", "q"):
                llm_intake_chat_messages = HumanMessage(content="Exiting.Goodbye!")
                return {"phase": "end", "pending_user_input": None, "messages": [llm_intake_chat_messages], "output": "Exiting.Goodbye!"}
            llm_intake_chat_messages = HumanMessage(content="The information was not correct. Entered new policy number.")
            return {"phase": "awaiting_policy", "user_input": user_input, "policy_details": {}, "pending_user_input": None, "messages": [llm_intake_chat_messages], "output": llm_intake_chat_messages.content}

        return {}
    
    return intake_node

def make_analysis_agent_node() -> Callable[[InsuranceCancellationState], Dict[str, Any]]:
    """
    Build the Analysis agent node: determine eligibility via cancellation_rules only (no refund calc).

    Reads: policy_details, phase. Writes: phase (human_eligibility_check or end), messages, output.
    Uses tools: cancellation_rules.
    """

    def analysis_node(state: InsuranceCancellationState) -> Dict[str, Any]:
        print("\n")
        print("  → Analysis node running (phase=%s)" % state.get("phase", "ready_for_analysis"))
        phase = state.get("phase", "ready_for_analysis")
        policy_details = state.get("policy_details", {})
        messages = state.get("messages", [])
        output = state.get("output", "")
        
        if not policy_details.get("is_policy_found", False):
            output = "Policy not found. Please try again."
            print(f"✅ {output}")
            return {"phase": "end", "messages": [HumanMessage(content=output)], "output": output}
        
        is_eligible, reason = check_cancellation_eligibility(policy_details)
        if not is_eligible:
            output = (
                f"Policy is not eligible for cancellation. "
                f"Reason: {reason}.\n"
                f"Stopping the workflow..."
            )
            print(f"✅ {output}")
            return {"phase": "end", "messages": [HumanMessage(content=output)], "output": output}
        
        output = (
            f"Policy is eligible for cancellation. "
            f"Reason: {reason}.\n"
            f"Moving to the human review..."
        )
        print(f"✅ {output}")
        return {"phase": "human_eligibility_check", "messages": [HumanMessage(content=output)], "output": output}

    return analysis_node

def make_refund_agent_node() -> Callable[[InsuranceCancellationState], Dict[str, Any]]:
    """
    Build the Refund agent node: check eligibility (cancellation_rules) and compute refund (refund_calculator).

    Reads: policy_details, phase. Writes: policy_details (with refund_amount, refund_reason), phase, messages, output.
    Uses tools: cancellation_rules, refund_calculator.
    """

    def refund_node(state: InsuranceCancellationState) -> Dict[str, Any]:
        print("\n")
        print("  → Refund node running (phase=%s)" % state.get("phase", "ready_for_refund"))
        phase = state.get("phase", "ready_for_refund")
        policy_details = state.get("policy_details", {})
        messages = state.get("messages", [])
        output = state.get("output", "")

        is_eligible, reason = check_cancellation_eligibility(policy_details)
        if not is_eligible:
            output = (
                f"Policy is not eligible for cancellation. "
                f"Reason: {reason}.\n"
                f"Stopping the workflow..."
            )
            print(f"✅ {output}")
            return {"phase": "end", "messages": [HumanMessage(content=output)], "output": output}

        is_refund_eligible, refund_reason, refund_amount = calculate_refund_amount(policy_details)
        if not is_refund_eligible:
            output = (
                f"Failed to calculate refund amount. "
                f"Reason: {refund_reason}\n"
                f"Stopping the workflow..."
            )
            print(f"✅ {output}")
            return {"phase": "end", "messages": [HumanMessage(content=output)], "output": output}

        output = (
            f"Refund calculation complete. {refund_reason} "
            f"Refund Amount: ${refund_amount}.\n"
            f"Moving to the human review..."
        )
        print(f"✅ {output}")
        policy_details_with_refund = {**policy_details, "refund_amount": refund_amount, "refund_reason": refund_reason}
        return {"phase": "human_refund_check", "policy_details": policy_details_with_refund, "messages": [HumanMessage(content=output)], "output": output}

    return refund_node


def make_logger_agent_node() -> Callable[[InsuranceCancellationState], Dict[str, Any]]:
    """
    Build the Log Refund node: append approved refund to CSV via refund_logger. No other side effects.

    Reads: policy_details (refund_amount, refund_reason). Writes: none (tool performs I/O).
    Uses tools: refund_logger. Called only after refund_hitl approval.
    """
    def logger_node(state: InsuranceCancellationState) -> Dict[str, Any]:
        policy_details = state.get("policy_details", {})
        refund_amount = policy_details.get("refund_amount", 0.0)
        refund_reason = policy_details.get("refund_reason", "")
        call_with_retry(
            log_refund_record,
            policy_details,
            refund_amount,
            refund_reason,
            name="refund_logger",
            stage="logger",
            log_args_preview=policy_details.get("policy_number", ""),
        )
        return {}

    return logger_node


def make_summary_agent_node(llm_model: str, llm_summary_prompt_config: Dict[str, Any]) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    """
    Build the Summary agent node: generate cancellation notice text (LLM) and PDF (notice_generator).

    Reads: policy_details, phase. Writes: phase (summary_complete), messages, output, pdf_path.
    Uses tools: notice_generator. LLM uses summary_assistant_prompt + policy/refund details.
    """

    llm = llm_model

    def summary_node(state: InsuranceCancellationState) -> Dict[str, Any]:
        print("\n")
        print("  → Summary node running (phase=%s)" % state.get("phase", "ready_for_summary"))
        phase = state.get("phase", "ready_for_summary")
        policy_details = state.get("policy_details", {})
        messages = state.get("messages", [])
        output = state.get("output", "")

        llm_summary_prompt = build_prompt_from_config(llm_summary_prompt_config, input_data=policy_details)

        llm_summary_chat_messages = [SystemMessage(content=llm_summary_prompt), HumanMessage(content=f"Please generate an insurance cancellation notice for the policy {policy_details.get('policy_number', '')}")]

        try:
            raw_notice = call_with_retry(
                lambda: llm.invoke(llm_summary_chat_messages).content,
                name="llm_invoke",
                stage="summary",
                log_args_preview=policy_details.get("policy_number", ""),
            )
            notice_text, output_valid = validate_output_with_guard(raw_notice)
            if not output_valid:
                log_compliance("output_filter", "summary", "Notice text replaced with safe fallback", validated=False)
        except Exception as e:
            log_compliance(
                "error_handling",
                "summary",
                "LLM or output validation failed after retries; using fallback notice",
                validated=False,
                error=str(e),
                metadata={"operation": "llm_invoke"},
            )
            notice_text = SAFE_NOTICE_FALLBACK

        refund_amount = policy_details.get("refund_amount", 0.0)
        refund_reason = policy_details.get("refund_reason", "")
        try:
            pdf_path = call_with_retry(
                generate_notice_pdf,
                policy_details,
                refund_amount,
                refund_reason,
                notice_text,
                name="notice_generator",
                stage="summary",
                log_args_preview=policy_details.get("policy_number", ""),
            )
        except Exception as e:
            log_compliance("error_handling", "summary", "PDF generation failed after retries", validated=False, error=str(e), metadata={"operation": "notice_generator"})
            pdf_path = "[PDF generation failed]"
        if pdf_path:
            print(f"✅ Notice generated successfully:\n   {pdf_path}")

        output = (
            f"Insurance cancellation for policy {policy_details.get('policy_number', '')} is completed successfully.\n   "
            f"Notice saved to: {pdf_path}"
        )
        print(f"✅ {output}")
        return {"phase": "summary_complete", "messages": llm_summary_chat_messages, "output": output, "pdf_path": pdf_path}

    return summary_node

def make_hitl_node(checkpoint_name: str) -> Callable[[InsuranceCancellationState], Dict[str, Any]]:
    """
    Build a HITL node that interrupts for human approval/reject, then on resume sets phase.

    checkpoint_name: "eligibility" or "refund" — identifies which checkpoint for routing.
    If state already has human_decision and hitl_checkpoint == checkpoint_name, does not
    interrupt again; returns phase (ready_for_refund or ready_for_summary on approve, end on reject).
    Otherwise returns interrupt({ instructions, payload }) so main can run run_human_review and update_state.
    """

    def hitl_node(state: InsuranceCancellationState) -> Dict[str, Any]:
        # Already have human decision for this checkpoint (we resumed after update_state) → don't interrupt again, set phase and let router run
        if state.get("human_decision") and state.get("hitl_checkpoint") == checkpoint_name:
            if state.get("human_decision") == "approved":
                next_phase = "ready_for_refund" if checkpoint_name == "eligibility" else "ready_for_summary"
                print(f"  → Human decides to approve {checkpoint_name}, proceeding (phase={next_phase}).")
                return {"phase": next_phase}
            else:
                next_phase = "end"
                print(f"  → Human decides to reject {checkpoint_name}, stopping the workflow.")
                return {"phase": "end"}

        print("\n")
        print(f"  → Human Review Required for {checkpoint_name}")

        policy_details = state.get("policy_details") or {}
        payload = {
            "checkpoint_name": checkpoint_name,
            "policy_details": policy_details,
            "policy_number": policy_details.get("policy_number", ""),
            "messages": state.get("messages", []),
            "output": state.get("output", ""),
            "summary": state.get("output", ""),
        }

        return interrupt({
            "messages": [HumanMessage(content=f"Human review required for checkpoint: {checkpoint_name}")],
            "instructions": "🧑 Please review the following information and decide if the refund should be approved or rejected.",
            "payload": payload,
        })

    return hitl_node