"""
End-to-end system tests for complete workflow flows.

Runs the full insurance cancellation graph (intake → analysis → HITL → refund → HITL →
logger → summary) with mocked user input, HITL decisions, and LLM. Verifies that
the entire flow completes and produces expected outputs (refund log, PDF notice).

Run with: pytest tests/test_e2e_system_flows.py -v -s
(-s disables output capture so mocked input() works.)
"""
import os
from unittest.mock import patch, MagicMock
import pytest

pytestmark = [pytest.mark.e2e]

from codes.state import InsuranceCancellationState
from codes.graph import build_insurance_cancellation_graph
from codes.utils import load_config
from codes.paths import PROMPT_CONFIG_FILE_PATH


def _mock_llm():
    """Return a mock LLM that returns a fixed notice text (used by summary node)."""
    mock = MagicMock()
    mock.invoke.return_value.content = (
        "Policy cancelled. Refund processed. Thank you for your business."
    )
    return mock


def _run_graph_to_completion(
    graph,
    config: dict,
    initial_state: InsuranceCancellationState,
    run_human_review_fn,
    intake_responses=None,
    max_iterations: int = 10,
):
    """
    Run the graph until it completes (no interrupt). Handles intake interrupts by
    feeding pending_user_input from intake_responses, and HITL by calling run_human_review_fn.
    Returns the final state or the state at last interrupt.
    """
    if intake_responses is None:
        intake_responses = []
    intake_iter = iter(intake_responses)
    state_input = initial_state
    for _ in range(max_iterations):
        result = graph.invoke(state_input, config=config)
        if not isinstance(result, dict):
            return result

        if "__interrupt__" in result:
            raw = result["__interrupt__"]
            item = raw[0] if isinstance(raw, list) and raw else raw
            if hasattr(item, "value"):
                interrupt_payload = item.value if isinstance(item.value, dict) else {}
            elif isinstance(item, dict):
                interrupt_payload = item
            else:
                interrupt_payload = {}

            # Intake interrupt: feed next response as pending_user_input
            if interrupt_payload.get("type") == "intake":
                try:
                    user_val = next(intake_iter)
                except StopIteration:
                    user_val = ""
                graph.update_state(config, {"pending_user_input": user_val})
                state_input = None
                continue

            # HITL interrupt
            state_vals = result.get("values", result)
            policy_details = state_vals.get("policy_details") or {}
            if not isinstance(policy_details, dict):
                policy_details = {}
            payload = interrupt_payload.get("payload", {}) or {}
            review_data = {
                **interrupt_payload,
                "payload": {**payload, "policy_details": policy_details},
            }
            human_out = run_human_review_fn(review_data, default_choice="a")
            graph.update_state(
                config,
                {
                    "human_decision": human_out["human_decision"],
                    "hitl_checkpoint": human_out["hitl_checkpoint"],
                },
            )
            state_input = None
            continue
        return result
    return result


class TestE2ECompleteFlowApproved:
    """Full flow: valid policy, confirm, approve both HITLs → summary_complete and outputs."""

    @pytest.fixture
    def prompt_config(self):
        if os.path.isfile(PROMPT_CONFIG_FILE_PATH):
            return load_config(PROMPT_CONFIG_FILE_PATH)
        return {
            "intake_assistant_prompt": {"role": "Assistant", "instruction": "Collect policy number."},
            "summary_assistant_prompt": {"role": "Assistant", "instruction": "Generate summary."},
        }

    @pytest.fixture
    def mock_llm(self):
        return _mock_llm()

    @pytest.fixture
    def input_responses(self):
        return ["POL01212", "yes", "a", "a"]

    def test_full_flow_completes_with_summary_and_outputs(
        self, tmp_path, monkeypatch, prompt_config, mock_llm, input_responses
    ):
        import codes.tools.refund_logger as refund_logger_module
        import codes.tools.notice_generator as notice_generator_module
        monkeypatch.setattr(refund_logger_module, "OUTPUTS_DIR", str(tmp_path))
        monkeypatch.setattr(
            refund_logger_module,
            "REFUND_LOG_FILE_PATH",
            os.path.join(str(tmp_path), "refund_log.csv"),
        )
        monkeypatch.setattr(notice_generator_module, "OUTPUTS_DIR", str(tmp_path))

        def run_human_review(interrupt_payload, default_choice=None):
            payload = interrupt_payload.get("payload", {}) or {}
            return {
                "human_decision": "approved",
                "human_notes": "Approved in E2E test",
                "hitl_checkpoint": payload.get("checkpoint_name", "eligibility"),
            }

        thread_id = "e2e-full-flow-1"
        run_config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}
        initial_state: InsuranceCancellationState = {
            "phase": "ask_policy",
            "policy_details": {},
            "user_input": "",
            "messages": [],
            "invalid_policy_attempts": 0,
        }

        graph = build_insurance_cancellation_graph(mock_llm, prompt_config)
        final = _run_graph_to_completion(
            graph, run_config, initial_state, run_human_review,
            intake_responses=["POL01212", "yes"],
        )

        vals = final.get("values", final) if isinstance(final, dict) else final
        if not isinstance(vals, dict):
            vals = {}
        phase = final.get("phase") or vals.get("phase")
        pdf_path = final.get("pdf_path") or vals.get("pdf_path")
        output = final.get("output") or vals.get("output")

        assert phase == "summary_complete", f"Expected summary_complete, got phase={phase}, keys={list(final.keys()) if isinstance(final, dict) else 'n/a'}"
        if pdf_path:
            assert os.path.isfile(pdf_path), f"Expected PDF at {pdf_path}"
            assert "POL01212" in pdf_path or "Cancellation_Notice" in pdf_path
        else:
            pdfs = list(tmp_path.glob("Cancellation_Notice_*.pdf"))
            assert pdfs, f"Expected PDF in {tmp_path}"
            assert any("POL01212" in p.name for p in pdfs)
        assert output is None or ("cancellation" in output.lower() or "completed" in output.lower())
        assert os.path.isfile(os.path.join(tmp_path, "refund_log.csv"))
        with open(os.path.join(tmp_path, "refund_log.csv"), encoding="utf-8") as f:
            log_content = f.read()
        assert "POL01212" in log_content


class TestE2EEligibilityRejected:
    """E2E: flow stops at eligibility HITL when human rejects."""

    @pytest.fixture
    def prompt_config(self):
        if os.path.isfile(PROMPT_CONFIG_FILE_PATH):
            return load_config(PROMPT_CONFIG_FILE_PATH)
        return {
            "intake_assistant_prompt": {"role": "A", "instruction": "Collect policy."},
            "summary_assistant_prompt": {"role": "A", "instruction": "Summarize."},
        }

    def test_flow_ends_after_eligibility_reject(self, tmp_path, monkeypatch, prompt_config):
        import codes.tools.refund_logger as refund_logger_module
        import codes.tools.notice_generator as notice_generator_module
        monkeypatch.setattr(refund_logger_module, "OUTPUTS_DIR", str(tmp_path))
        monkeypatch.setattr(
            refund_logger_module,
            "REFUND_LOG_FILE_PATH",
            os.path.join(str(tmp_path), "refund_log.csv"),
        )
        monkeypatch.setattr(notice_generator_module, "OUTPUTS_DIR", str(tmp_path))

        call_count = [0]

        def run_human_review_reject_eligibility(interrupt_payload, default_choice=None):
            call_count[0] += 1
            payload = interrupt_payload.get("payload", {}) or {}
            checkpoint = payload.get("checkpoint_name", "eligibility")
            return {
                "human_decision": "rejected" if checkpoint == "eligibility" else "approved",
                "human_notes": "Rejected in E2E test",
                "hitl_checkpoint": checkpoint,
            }

        mock_llm = _mock_llm()
        run_config = {"configurable": {"thread_id": "e2e-reject-1"}, "recursion_limit": 50}
        initial_state: InsuranceCancellationState = {
            "phase": "ask_policy",
            "policy_details": {},
            "user_input": "",
            "messages": [],
            "invalid_policy_attempts": 0,
        }
        graph = build_insurance_cancellation_graph(mock_llm, prompt_config)
        final = _run_graph_to_completion(
            graph, run_config, initial_state, run_human_review_reject_eligibility,
            intake_responses=["POL01212", "yes"],
        )

        vals = final.get("values", final)
        phase = vals.get("phase") if isinstance(vals, dict) else getattr(final, "phase", None)
        assert phase == "end"
        assert not os.path.isfile(os.path.join(tmp_path, "refund_log.csv"))


class TestE2EInvalidPolicyMaxAttempts:
    """E2E: intake ends with end when policy not found after max attempts."""

    @pytest.fixture
    def prompt_config(self):
        return {
            "intake_assistant_prompt": {"role": "A", "instruction": "Collect policy."},
            "summary_assistant_prompt": {"role": "A", "instruction": "Summarize."},
        }

    def test_flow_ends_after_max_invalid_policy_attempts(self, prompt_config):
        mock_llm = _mock_llm()
        run_config = {"configurable": {"thread_id": "e2e-max-attempts-1"}, "recursion_limit": 30}
        initial_state: InsuranceCancellationState = {
            "phase": "ask_policy",
            "policy_details": {},
            "user_input": "",
            "messages": [],
            "invalid_policy_attempts": 0,
        }
        # Intake interrupts for policy number; feed invalid numbers until max attempts (3) then phase=end
        graph = build_insurance_cancellation_graph(mock_llm, prompt_config)
        intake_responses = ["INVALID1", "INVALID2", "INVALID3"]
        intake_iter = iter(intake_responses)
        state_input = initial_state
        final = None
        for _ in range(10):
            result = graph.invoke(state_input, config=run_config)
            if not isinstance(result, dict):
                final = result
                break
            if "__interrupt__" not in result:
                final = result
                break
            raw = result["__interrupt__"]
            item = raw[0] if isinstance(raw, list) and raw else raw
            payload = item.value if hasattr(item, "value") else (item if isinstance(item, dict) else {})
            if isinstance(payload, dict) and payload.get("type") == "intake":
                try:
                    user_val = next(intake_iter)
                except StopIteration:
                    user_val = ""
                graph.update_state(run_config, {"pending_user_input": user_val})
                state_input = None
            else:
                graph.update_state(run_config, {"human_decision": "approved", "hitl_checkpoint": payload.get("payload", {}).get("checkpoint_name", "eligibility")})
                state_input = None
        assert final is not None
        vals = final.get("values", final) if isinstance(final, dict) else {}
        phase = vals.get("phase") if isinstance(vals, dict) else (final.get("phase") if isinstance(final, dict) else None)
        assert phase == "end", f"Expected phase end, got {phase}"
        invalid_attempts = vals.get("invalid_policy_attempts", 0) if isinstance(vals, dict) else 0
        assert invalid_attempts >= 3
