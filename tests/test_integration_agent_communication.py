"""
Integration tests for agent-to-agent communication.

These tests verify that state produced by one agent is correctly consumed by the next:
- Intake → Analysis (via phase ready_for_analysis and policy_details)
- Analysis → Eligibility HITL (via phase human_eligibility_check)
- Eligibility HITL (approved) → Refund (via phase ready_for_refund)
- Refund → Refund HITL (via phase human_refund_check and policy_details with refund)
- Refund HITL (approved) → Log refund → Summary

We test state handoff by running agent nodes in sequence with merged state,
and we test that graph routers choose the correct next node given each agent's output.
"""
import pytest

from codes.graph import (
    route_from_intake,
    route_from_analysis,
    route_from_refund,
    route_after_human,
)
from codes.nodes import (
    make_analysis_agent_node,
    make_refund_agent_node,
    make_log_refund_node,
    make_hitl_node,
)
from codes.tools.cancellation_rules import DATE_FORMAT
from codes.tools.data_lookup import lookup_policy_in_csv


def _eligible_policy_details(policy_number: str = "POL01212"):
    """Build policy_details as Intake would produce (from CSV), eligible for cancellation."""
    record = lookup_policy_in_csv(policy_number)
    if not record:
        raise ValueError(f"Policy {policy_number} not in CSV")
    is_paid = record.get("Is Payment Made", "")
    is_payment_made = is_paid.upper() in ("TRUE", "YES", "1") if isinstance(is_paid, str) else bool(is_paid)
    return {
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


def _merge_state(state: dict, updates: dict) -> dict:
    """Merge agent output updates into state (simplified; LangGraph uses add_messages for messages)."""
    merged = {**state}
    for k, v in updates.items():
        if k == "messages" and (state.get("messages") or updates.get("messages")):
            merged["messages"] = list(state.get("messages", [])) + list(updates.get("messages", []))
        else:
            merged[k] = v
    return merged


# ----- Router integration tests: agent output state → correct next node -----


class TestRouterAgentToAgent:
    """Routers must send to the correct next agent given state from the previous agent."""

    def test_after_intake_ready_for_analysis_routes_to_analysis(self):
        state = {"phase": "ready_for_analysis", "policy_details": _eligible_policy_details()}
        assert route_from_intake(state) == "analysis"

    def test_after_intake_awaiting_policy_routes_back_to_intake(self):
        state = {"phase": "awaiting_policy", "user_input": "POL01212"}
        assert route_from_intake(state) == "intake"

    def test_after_intake_end_routes_to_end(self):
        state = {"phase": "end"}
        assert route_from_intake(state) == "end"

    def test_after_analysis_eligible_routes_to_eligibility_hitl(self):
        state = {"phase": "human_eligibility_check", "output": "Policy is eligible..."}
        assert route_from_analysis(state) == "eligibility_hitl"

    def test_after_analysis_not_eligible_routes_to_end(self):
        state = {"phase": "end", "output": "Policy is not eligible"}
        assert route_from_analysis(state) == "end"

    def test_after_refund_calculated_routes_to_refund_hitl(self):
        state = {"phase": "human_refund_check", "policy_details": {"refund_amount": 100.0}}
        assert route_from_refund(state) == "refund_hitl"

    def test_after_eligibility_hitl_approved_routes_to_refund(self):
        state = {"human_decision": "approved", "hitl_checkpoint": "eligibility", "phase": "ready_for_refund"}
        assert route_after_human(state) == "refund"

    def test_after_eligibility_hitl_rejected_routes_to_end(self):
        state = {"human_decision": "rejected", "hitl_checkpoint": "eligibility"}
        assert route_after_human(state) == "end"

    def test_after_refund_hitl_approved_routes_to_log_refund(self):
        state = {"human_decision": "approved", "hitl_checkpoint": "refund", "phase": "ready_for_summary"}
        assert route_after_human(state) == "log_refund"


# ----- State handoff integration: one agent's output → next agent's input -----


class TestAnalysisReceivesIntakeOutput:
    """Analysis agent must correctly consume state produced by Intake."""

    def test_analysis_receives_ready_for_analysis_and_produces_eligibility_check(self):
        intake_output_state = {
            "phase": "ready_for_analysis",
            "policy_details": _eligible_policy_details("POL01212"),
            "messages": [],
        }
        analysis_node = make_analysis_agent_node()
        out = analysis_node(intake_output_state)
        assert out["phase"] == "human_eligibility_check"
        assert "eligible" in out["output"].lower()
        assert len(out["messages"]) == 1

    def test_analysis_receives_ineligible_policy_produces_end(self):
        policy = _eligible_policy_details("POL01212")
        policy["policy_status"] = "Cancelled"
        intake_output_state = {"phase": "ready_for_analysis", "policy_details": policy}
        analysis_node = make_analysis_agent_node()
        out = analysis_node(intake_output_state)
        assert out["phase"] == "end"
        assert "not eligible" in out["output"].lower() or "not active" in out["output"].lower()


class TestRefundReceivesEligibilityHitlOutput:
    """Refund agent must correctly consume state after Eligibility HITL approval."""

    def test_refund_receives_ready_for_refund_and_produces_refund_hitl_state(self):
        policy = _eligible_policy_details("POL01212")
        state_after_eligibility_hitl = {
            "phase": "ready_for_refund",
            "policy_details": policy,
            "human_decision": "approved",
            "hitl_checkpoint": "eligibility",
        }
        refund_node = make_refund_agent_node()
        out = refund_node(state_after_eligibility_hitl)
        assert out["phase"] == "human_refund_check"
        assert "refund_amount" in out["policy_details"]
        assert "refund_reason" in out["policy_details"]
        assert out["policy_details"]["refund_amount"] >= 0


class TestLogRefundReceivesRefundHitlOutput:
    """Log refund agent must correctly consume state after Refund HITL approval."""

    def test_log_refund_receives_policy_details_with_refund_and_persists(self, tmp_path, monkeypatch):
        import codes.tools.refund_logger as refund_logger_module
        monkeypatch.setattr(refund_logger_module, "OUTPUTS_DIR", str(tmp_path))
        monkeypatch.setattr(
            refund_logger_module,
            "REFUND_LOG_FILE_PATH",
            str(tmp_path / "refund_log.csv"),
        )
        policy = _eligible_policy_details("POL01212")
        policy["refund_amount"] = 250.50
        policy["refund_reason"] = "Refund amount calculated successfully."
        state_after_refund_hitl = {"policy_details": policy}
        log_refund_node = make_log_refund_node()
        out = log_refund_node(state_after_refund_hitl)
        assert out == {}
        assert (tmp_path / "refund_log.csv").exists()
        with open(tmp_path / "refund_log.csv", encoding="utf-8") as f:
            content = f.read()
        assert "POL01212" in content
        assert "250.5" in content


# ----- Multi-agent chain: state flows through several agents -----


class TestMultiAgentChain:
    """State must flow correctly through multiple agents in sequence."""

    def test_analysis_then_refund_chain_with_merged_state(self):
        analysis_node = make_analysis_agent_node()
        refund_node = make_refund_agent_node()
        state = {
            "phase": "ready_for_analysis",
            "policy_details": _eligible_policy_details("POL01212"),
            "messages": [],
        }
        analysis_out = analysis_node(state)
        merged = _merge_state(state, analysis_out)
        assert merged["phase"] == "human_eligibility_check"
        # Simulate HITL approval: set phase and decision for next step
        merged["phase"] = "ready_for_refund"
        merged["human_decision"] = "approved"
        merged["hitl_checkpoint"] = "eligibility"
        refund_out = refund_node(merged)
        merged2 = _merge_state(merged, refund_out)
        assert merged2["phase"] == "human_refund_check"
        assert "refund_amount" in merged2["policy_details"]
        assert merged2["policy_details"]["refund_amount"] >= 0

    def test_analysis_refund_log_refund_chain(self, tmp_path, monkeypatch):
        import codes.tools.refund_logger as refund_logger_module
        monkeypatch.setattr(refund_logger_module, "OUTPUTS_DIR", str(tmp_path))
        monkeypatch.setattr(
            refund_logger_module,
            "REFUND_LOG_FILE_PATH",
            str(tmp_path / "refund_log.csv"),
        )
        analysis_node = make_analysis_agent_node()
        refund_node = make_refund_agent_node()
        log_refund_node = make_log_refund_node()
        state = {
            "phase": "ready_for_analysis",
            "policy_details": _eligible_policy_details("POL02309"),
            "messages": [],
        }
        state = _merge_state(state, analysis_node(state))
        state["phase"] = "ready_for_refund"
        state["human_decision"] = "approved"
        state["hitl_checkpoint"] = "eligibility"
        state = _merge_state(state, refund_node(state))
        state["phase"] = "ready_for_summary"
        state["human_decision"] = "approved"
        state["hitl_checkpoint"] = "refund"
        log_out = log_refund_node(state)
        state = _merge_state(state, log_out)
        assert (tmp_path / "refund_log.csv").exists()
        with open(tmp_path / "refund_log.csv", encoding="utf-8") as f:
            lines = f.readlines()
        assert any("POL02309" in line for line in lines)


# ----- HITL agent: resume state handoff -----


class TestHitlResumeHandoff:
    """HITL nodes must set phase correctly when resuming after human decision."""

    def test_eligibility_hitl_with_approved_sets_ready_for_refund(self):
        hitl_node = make_hitl_node("eligibility")
        state = {"human_decision": "approved", "hitl_checkpoint": "eligibility", "policy_details": {}}
        out = hitl_node(state)
        assert out["phase"] == "ready_for_refund"

    def test_eligibility_hitl_with_rejected_sets_end(self):
        hitl_node = make_hitl_node("eligibility")
        state = {"human_decision": "rejected", "hitl_checkpoint": "eligibility"}
        out = hitl_node(state)
        assert out["phase"] == "end"

    def test_refund_hitl_with_approved_sets_ready_for_summary(self):
        hitl_node = make_hitl_node("refund")
        state = {"human_decision": "approved", "hitl_checkpoint": "refund", "policy_details": {}}
        out = hitl_node(state)
        assert out["phase"] == "ready_for_summary"
