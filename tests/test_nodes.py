"""Unit tests for agent node functions (analysis, refund, logger, hitl)."""
from datetime import datetime, timedelta
from unittest.mock import patch
import pytest

from langchain_core.messages import HumanMessage

from codes.nodes import (
    make_analysis_agent_node,
    make_refund_agent_node,
    make_logger_agent_node,
    make_hitl_node,
)
from codes.tools.cancellation_rules import DATE_FORMAT


def _policy_details(eligible=True, payment_made=True, end_date_future=True):
    end = datetime.now() + timedelta(days=30) if end_date_future else datetime.now() - timedelta(days=1)
    return {
        "is_policy_found": True,
        "policy_number": "POL01212",
        "policy_status": "active" if eligible else "Cancelled",
        "is_payment_made": payment_made,
        "end_date": end.strftime(DATE_FORMAT),
        "start_date": (datetime.now() - timedelta(days=30)).strftime(DATE_FORMAT),
        "payment_amount": 600.0,
        "first_name": "John",
        "last_name": "Smith",
        "email": "john@example.com",
    }


class TestAnalysisNode:
    """Test make_analysis_agent_node."""

    def test_analysis_eligible_sets_phase_human_eligibility_check(self):
        node = make_analysis_agent_node()
        state = {"phase": "ready_for_analysis", "policy_details": _policy_details()}
        out = node(state)
        assert out["phase"] == "human_eligibility_check"
        assert "eligible" in out["output"].lower()
        assert len(out["messages"]) == 1

    def test_analysis_not_eligible_sets_phase_end(self):
        node = make_analysis_agent_node()
        state = {"phase": "ready_for_analysis", "policy_details": _policy_details(eligible=False)}
        out = node(state)
        assert out["phase"] == "end"
        assert "not eligible" in out["output"].lower() or "not active" in out["output"].lower()

    def test_analysis_policy_not_found_sets_phase_end(self):
        node = make_analysis_agent_node()
        state = {"phase": "ready_for_analysis", "policy_details": {"is_policy_found": False}}
        out = node(state)
        assert out["phase"] == "end"
        assert "not found" in out["output"].lower() or "try again" in out["output"].lower()


class TestRefundNode:
    """Test make_refund_agent_node."""

    def test_refund_eligible_sets_phase_and_refund_in_policy_details(self):
        node = make_refund_agent_node()
        policy = _policy_details()
        state = {"phase": "ready_for_refund", "policy_details": policy}
        out = node(state)
        assert out["phase"] == "human_refund_check"
        assert "refund_amount" in out["policy_details"]
        assert "refund_reason" in out["policy_details"]
        assert out["policy_details"]["refund_amount"] >= 0

    def test_refund_not_eligible_sets_phase_end(self):
        node = make_refund_agent_node()
        state = {"phase": "ready_for_refund", "policy_details": _policy_details(eligible=False)}
        out = node(state)
        assert out["phase"] == "end"


class TestLogRefundNode:
    """Test make_logger_agent_node with temp output dir."""

    def test_log_refund_node_calls_logger_and_returns_empty_updates(self, tmp_path, monkeypatch):
        from codes.tools import refund_logger as refund_logger_module
        monkeypatch.setattr(refund_logger_module, "OUTPUTS_DIR", str(tmp_path))
        monkeypatch.setattr(
            refund_logger_module,
            "REFUND_LOG_FILE_PATH",
            str(tmp_path / "refund_log.csv"),
        )
        node = make_logger_agent_node()
        state = {
            "policy_details": {
                "policy_number": "POL001",
                "first_name": "A",
                "last_name": "B",
                "email": "a@b.com",
                "refund_amount": 100.0,
                "refund_reason": "Test reason",
            }
        }
        out = node(state)
        assert out == {}
        assert (tmp_path / "refund_log.csv").exists()


class TestHitlNode:
    """Test make_hitl_node (eligibility and refund checkpoints)."""

    def test_hitl_with_approved_decision_eligibility_sets_ready_for_refund(self):
        node = make_hitl_node("eligibility")
        state = {
            "human_decision": "approved",
            "hitl_checkpoint": "eligibility",
            "policy_details": {},
        }
        out = node(state)
        assert out["phase"] == "ready_for_refund"

    def test_hitl_with_approved_decision_refund_sets_ready_for_summary(self):
        node = make_hitl_node("refund")
        state = {
            "human_decision": "approved",
            "hitl_checkpoint": "refund",
            "policy_details": {},
        }
        out = node(state)
        assert out["phase"] == "ready_for_summary"

    def test_hitl_with_reject_sets_phase_end(self):
        node = make_hitl_node("eligibility")
        state = {
            "human_decision": "rejected",
            "hitl_checkpoint": "eligibility",
        }
        out = node(state)
        assert out["phase"] == "end"

    def test_hitl_without_decision_returns_interrupt(self):
        # interrupt() requires a LangGraph runnable context; mock it to return the payload dict
        with patch("codes.nodes.interrupt", side_effect=lambda x: x):
            node = make_hitl_node("eligibility")
            state = {"policy_details": {"policy_number": "POL001"}, "messages": [], "output": ""}
            out = node(state)
        assert "payload" in out
        assert "instructions" in out
        assert out["payload"].get("checkpoint_name") == "eligibility"
