"""
Application entry point — run the insurance cancellation multi-agent workflow.

Responsibilities:
  - Load config and prompt config (paths from paths.py), initialize LLM (llm.get_llm).
  - Build the graph (graph.build_insurance_cancellation_graph) and invoke with initial state.
  - When the graph interrupts (human-in-the-loop): show review UI (hitl_cli.run_human_review),
    then update state with human decision and resume (graph.update_state + invoke with None).
  - Save graph visualization to outputs/ when the run completes.

Usage: Run from project root; ensure config/config.yaml and config/prompt_config.yaml exist.
Environment: HITL_CHOICE=a|r for non-interactive approval/reject; --approve/--reject as CLI fallback.
"""
import sys
import os

# Ensure project root is on path when running as script from codes/ (e.g. python main.py)
if __name__ == "__main__" or "codes" not in sys.modules:
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

from typing import Any, Dict, Sequence
from pprint import pprint
from codes.utils import load_config, load_csv, ConfigError
from codes.llm import get_llm
from codes.paths import CONFIG_FILE_PATH, PROMPT_CONFIG_FILE_PATH, OUTPUTS_DIR

from codes.state import InsuranceCancellationState
from codes.graph import build_insurance_cancellation_graph
from codes.output_graph import save_graph_visualization
from codes.hitl_cli import run_human_review


def _run_health_and_exit() -> None:
    """Run health checks and print results; exit 0 if ok, 1 otherwise."""
    try:
        from codes.health import run_health_checks
    except ImportError as e:
        print(f"Health check unavailable: {e}")
        sys.exit(1)
    out = run_health_checks(skip_llm=True, verbose=True)
    for r in out["results"]:
        status = "ok" if r["ok"] else "FAIL"
        if r.get("skipped"):
            status = "skip"
        print(f"  [{status}] {r['name']}: {r['message']}")
        for d in r.get("details", []):
            print(f"    - {d}")
    if not out["ok"]:
        sys.exit(1)
    print("All health checks passed.")
    sys.exit(0)


def get_hitl_choice_from_argv():
    """
    Parse --approve or --reject from command line for non-interactive HITL.

    Returns:
        "a" for approve, "r" for reject, or None if not specified.
    """
    for arg in sys.argv[1:]:
        a = arg.strip().lower()
        if a in ("--approve", "-a"):
            return "a"
        if a in ("--reject", "-r"):
            return "r"
    return None


def main() -> None:
    """
    Run the insurance cancellation graph to completion (with HITL when interrupted).

    Flow: Initialize config and LLM → invoke graph with initial_state → on __interrupt__,
    run human review, update_state with decision, invoke again with None to resume →
    repeat until no interrupt; then save graph PNG and exit.
    """
    if "--health" in sys.argv or "-H" in sys.argv:
        _run_health_and_exit()

    print("=" * 80)
    print("🔍 Insurance Cancellation System")
    print("=" * 80)
    try:
        config = load_config(CONFIG_FILE_PATH)
        prompt_config = load_config(PROMPT_CONFIG_FILE_PATH)
    except ConfigError as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)
    request_timeout = config.get("request_timeout")
    if request_timeout is not None:
        request_timeout = float(request_timeout)
    try:
        llm_model = get_llm(config["llm_model"], 0.3, request_timeout=request_timeout)
    except Exception as e:
        print(f"❌ Failed to initialize LLM: {e}")
        sys.exit(1)
    print(f"✅ LLM initialized: {llm_model.model_name}")

    initial_state: InsuranceCancellationState = {
        "phase": "ask_policy",
        "policy_details": {},
        "user_input": "",
        "messages": [],
        "invalid_policy_attempts": 0,
    }

    print("🔍 Running graph...")
    graph = build_insurance_cancellation_graph(llm_model, prompt_config)
    run_config = {"configurable": {"thread_id": "insurance-cancel-1"}, "recursion_limit": 50}

    try:
        while True:
            try:
                final_state = graph.invoke(initial_state, config=run_config)
            except Exception as e:
                print(f"❌ Graph error: {e}")
                sys.exit(1)

            if "__interrupt__" in final_state:
                raw = final_state["__interrupt__"]
                item = raw[0] if isinstance(raw, list) and raw else raw
                if hasattr(item, "value"):
                    interrupt_payload = item.value if isinstance(item.value, dict) else {}
                elif isinstance(item, dict):
                    interrupt_payload = item
                else:
                    interrupt_payload = {}

                if interrupt_payload.get("type") == "intake":
                    kind = interrupt_payload.get("input_kind", "")
                    msg = interrupt_payload.get("message", "Input required.")
                    print(msg)
                    try:
                        user_val = input().strip()
                    except (EOFError, KeyboardInterrupt):
                        print("\nExiting.")
                        sys.exit(0)
                    graph.update_state(run_config, {"pending_user_input": user_val})
                    initial_state = None
                    continue

                state_vals = final_state if isinstance(final_state.get("policy_details"), dict) else final_state.get("values", final_state)
                policy_details = state_vals.get("policy_details") or {}
                if not isinstance(policy_details, dict) and hasattr(policy_details, "items"):
                    policy_details = dict(policy_details)
                elif not isinstance(policy_details, dict):
                    policy_details = {}
                payload = interrupt_payload.get("payload", {}) or {}
                output_text = state_vals.get("output", payload.get("output", ""))
                review_data = {
                    **interrupt_payload,
                    "payload": {
                        **payload,
                        "policy_details": policy_details,
                        "policy_number": policy_details.get("policy_number", payload.get("policy_number", "")),
                        "output": output_text,
                        "summary": output_text,
                    },
                }
                hitl_choice = get_hitl_choice_from_argv() or os.environ.get("HITL_CHOICE")
                human_input = run_human_review(review_data, default_choice=hitl_choice)
                graph.update_state(
                    run_config,
                    {"human_decision": human_input["human_decision"], "hitl_checkpoint": human_input["hitl_checkpoint"]},
                )
                initial_state = None
                continue
            break

        try:
            save_graph_visualization(graph, save_dir=OUTPUTS_DIR, graph_name="insurance_cancellation_graph")
        except Exception as e:
            print(f"⚠️ Could not save graph visualization: {e}")

        print("\n✅ Graph completed successfully")
    except KeyboardInterrupt:
        print("\nExiting.")
        sys.exit(0)
    print("=" * 80)


if __name__ == "__main__":
    main()