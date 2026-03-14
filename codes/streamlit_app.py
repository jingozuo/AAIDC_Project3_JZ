"""
Streamlit UI for the insurance cancellation workflow.

Run from project root: streamlit run codes/streamlit_app.py

Handles intake interrupts (policy number, confirm yes/no, correct policy) and
HITL interrupts (eligibility and refund approval) via forms and buttons.
"""
import sys
import os

# Ensure project root is on path when run as streamlit run codes/streamlit_app.py
if getattr(sys, "frozen", False) is False:
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

import streamlit as st
from codes.utils import load_config, ConfigError
from codes.paths import CONFIG_FILE_PATH, PROMPT_CONFIG_FILE_PATH, OUTPUTS_DIR
from codes.llm import get_llm
from codes.state import InsuranceCancellationState
from codes.graph import build_insurance_cancellation_graph
from codes.output_graph import save_graph_visualization


def _ensure_session():
    if "graph" not in st.session_state:
        if "init_error" in st.session_state:
            return  # Already failed; show error in UI
        try:
            config = load_config(CONFIG_FILE_PATH)
            prompt_config = load_config(PROMPT_CONFIG_FILE_PATH)
        except ConfigError as e:
            st.session_state.init_error = f"Configuration error: {e}"
            return
        except Exception as e:
            st.session_state.init_error = f"Failed to load config: {e}"
            return
        try:
            request_timeout = config.get("request_timeout")
            if request_timeout is not None:
                request_timeout = float(request_timeout)
            llm = get_llm(config["llm_model"], 0.3, request_timeout=request_timeout)
        except Exception as e:
            st.session_state.init_error = f"Failed to initialize LLM: {e}"
            return
        st.session_state.graph = build_insurance_cancellation_graph(llm, prompt_config)
        st.session_state.config = {"configurable": {"thread_id": "streamlit-1"}, "recursion_limit": 50}
        st.session_state.messages = []
        st.session_state.done = False
        st.session_state.interrupt_payload = None
        st.session_state.last_output = ""


def _get_interrupt_from_state(final_state):
    if "__interrupt__" not in final_state:
        return None
    raw = final_state["__interrupt__"]
    item = raw[0] if isinstance(raw, list) and raw else raw
    if hasattr(item, "value"):
        return item.value if isinstance(item.value, dict) else {}
    return item if isinstance(item, dict) else {}


def _run_graph(initial_state):
    _ensure_session()
    graph = st.session_state.graph
    config = st.session_state.config
    try:
        final = graph.invoke(initial_state, config=config)
    except Exception as e:
        st.error(f"Graph error: {e}")
        return None, None
    state_vals = final if isinstance(final.get("policy_details"), dict) else final.get("values", final)
    output = (state_vals or {}).get("output", "")
    return final, output


def main():
    st.set_page_config(page_title="Insurance Cancellation", page_icon="📋", layout="centered")
    st.title("📋 Insurance Cancellation")
    st.caption("Multi-agent workflow: policy lookup → eligibility → refund → notice")

    _ensure_session()
    if st.session_state.get("init_error"):
        st.error(st.session_state.init_error)
        st.info("Check that config/config.yaml and config/prompt_config.yaml exist and are valid. For LLM errors, check API keys.")
        return

    if st.sidebar.button("🔄 New session"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

    # Show conversation so far
    for msg in st.session_state.get("messages", []):
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # If workflow is done, show final message and optional graph save
    if st.session_state.get("done"):
        st.success("Workflow completed.")
        if st.sidebar.button("Save graph PNG"):
            try:
                save_graph_visualization(st.session_state.graph, save_dir=OUTPUTS_DIR, graph_name="insurance_cancellation_graph")
                st.sidebar.success("Saved to outputs/")
            except Exception as e:
                st.sidebar.error(str(e))
        return

    interrupt_payload = st.session_state.get("interrupt_payload")

    # Intake interrupt: show form for policy number, confirm, or correct policy
    if interrupt_payload and interrupt_payload.get("type") == "intake":
        kind = interrupt_payload.get("input_kind", "")
        msg = interrupt_payload.get("message", "Input required.")
        st.info(msg)
        policy_details = interrupt_payload.get("policy_details") or {}
        if policy_details:
            st.json(policy_details)

        if kind == "confirm":
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Yes, confirm"):
                    st.session_state.graph.update_state(st.session_state.config, {"pending_user_input": "yes"})
                    st.session_state.interrupt_payload = None
                    st.session_state.messages.append({"role": "user", "content": "Yes, confirm"})
                    final, out = _run_graph(None)
                    if out:
                        st.session_state.messages.append({"role": "assistant", "content": out})
                    if final and "__interrupt__" in final:
                        st.session_state.interrupt_payload = _get_interrupt_from_state(final)
                    else:
                        st.session_state.done = "__interrupt__" not in (final or {})
                    st.rerun()
            with col2:
                if st.button("No, re-enter policy"):
                    st.session_state.graph.update_state(st.session_state.config, {"pending_user_input": "no"})
                    st.session_state.interrupt_payload = None
                    st.session_state.messages.append({"role": "user", "content": "No"})
                    final, out = _run_graph(None)
                    if out:
                        st.session_state.messages.append({"role": "assistant", "content": out})
                    if final and "__interrupt__" in final:
                        st.session_state.interrupt_payload = _get_interrupt_from_state(final)
                    else:
                        st.session_state.done = "__interrupt__" not in (final or {})
                    st.rerun()
        else:
            # policy_number, retry_policy, correct_policy: text input
            user_input = st.text_input("Your input", key="intake_input")
            if st.button("Submit"):
                if not (user_input or "").strip():
                    st.warning("Please enter a value.")
                else:
                    st.session_state.graph.update_state(st.session_state.config, {"pending_user_input": user_input.strip()})
                    st.session_state.interrupt_payload = None
                    st.session_state.messages.append({"role": "user", "content": user_input.strip()})
                    final, out = _run_graph(None)
                    if out:
                        st.session_state.messages.append({"role": "assistant", "content": out})
                    if final and "__interrupt__" in final:
                        st.session_state.interrupt_payload = _get_interrupt_from_state(final)
                    else:
                        st.session_state.done = "__interrupt__" not in (final or {})
                    st.rerun()
        return

    # HITL interrupt: show summary and Approve / Reject
    if interrupt_payload and interrupt_payload.get("type") != "intake":
        payload = interrupt_payload.get("payload", {})
        st.subheader("Human review")
        st.write(payload.get("output", payload.get("summary", "Review the following.")))
        st.json(payload.get("policy_details", {}))
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Approve"):
                st.session_state.graph.update_state(
                    st.session_state.config,
                    {"human_decision": "approved", "hitl_checkpoint": payload.get("checkpoint_name")},
                )
                st.session_state.interrupt_payload = None
                st.session_state.messages.append({"role": "user", "content": "Approved"})
                final, out = _run_graph(None)
                if out:
                    st.session_state.messages.append({"role": "assistant", "content": out})
                if final and "__interrupt__" in final:
                    st.session_state.interrupt_payload = _get_interrupt_from_state(final)
                else:
                    st.session_state.done = "__interrupt__" not in (final or {})
                st.rerun()
        with col2:
            if st.button("Reject"):
                st.session_state.graph.update_state(
                    st.session_state.config,
                    {"human_decision": "rejected", "hitl_checkpoint": payload.get("checkpoint_name")},
                )
                st.session_state.interrupt_payload = None
                st.session_state.done = True
                st.session_state.messages.append({"role": "user", "content": "Rejected"})
                st.session_state.messages.append({"role": "assistant", "content": "Workflow rejected."})
                st.rerun()
        return

    # No interrupt: start or continue. If we have no messages yet, run once to get first interrupt (ask policy).
    if not st.session_state.get("messages"):
        with st.spinner("Starting..."):
            initial: InsuranceCancellationState = {
                "phase": "ask_policy",
                "policy_details": {},
                "user_input": "",
                "messages": [],
                "invalid_policy_attempts": 0,
            }
            final, out = _run_graph(initial)
        if final and "__interrupt__" in final:
            st.session_state.interrupt_payload = _get_interrupt_from_state(final)
            if out:
                st.session_state.messages.append({"role": "assistant", "content": out})
            else:
                st.session_state.messages.append({"role": "assistant", "content": "Please provide your policy number to start."})
        elif final:
            st.session_state.done = True
            if out:
                st.session_state.messages.append({"role": "assistant", "content": out})
        st.rerun()

    # Show last output if any and we're not in a special interrupt UI
    if st.session_state.get("last_output"):
        with st.chat_message("assistant"):
            st.write(st.session_state.last_output)


if __name__ == "__main__":
    main()
