"""
Graph definition — LangGraph structure and conditional routing for the cancellation workflow.

This module builds the StateGraph: nodes (from nodes.py), edges, and conditional
routing. All routing is phase-based (state.phase). Checkpointer (MemorySaver) is
required for interrupt/resume and update_state (human-in-the-loop).

Node order: START → intake (self-loop) → analysis → eligibility_hitl → refund →
refund_hitl → log_refund → summary → END. Routers: route_from_intake, route_from_analysis,
route_from_refund, route_after_human (shared by both HITL nodes).
"""
from typing import Any, Dict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from codes.llm import get_llm
from codes.paths import CONFIG_FILE_PATH, PROMPT_CONFIG_FILE_PATH

from codes.state import InsuranceCancellationState
from codes.nodes import (
    make_intake_agent_node,
    make_analysis_agent_node,
    make_refund_agent_node,
    make_logger_agent_node,
    make_summary_agent_node,
    make_hitl_node
)


def route_from_intake(state: InsuranceCancellationState) -> str:
    """
    Route after intake node: loop back to intake or go to analysis or end.

    Returns:
        "intake" while phase is ask_policy | awaiting_policy | confirm_customer;
        "analysis" when phase is ready_for_analysis; "end" otherwise.
    """
    phase = state.get("phase")
    if phase in ("ask_policy", "awaiting_policy", "confirm_customer"):
        return "intake"
    if phase in ("ready_for_analysis",):
        return "analysis"
    return "end"


def route_from_analysis(state: InsuranceCancellationState) -> str:
    """
    Route after analysis: send to eligibility HITL when phase is human_eligibility_check.
    """
    phase = state.get("phase")
    if phase in ("human_eligibility_check",):
        return "eligibility_hitl"
    return "end"


def route_from_refund(state: InsuranceCancellationState) -> str:
    """
    Route after refund: send to refund HITL when phase is human_refund_check.
    """
    phase = state.get("phase")
    if phase in ("human_refund_check",):
        return "refund_hitl"
    return "end"


def route_after_human(state: InsuranceCancellationState) -> str:
    """
    Shared router for both HITL nodes: after human decision, go to refund, log_refund, or end.

    If human_decision != "approved", returns "end". If approved: eligibility → "refund",
    refund → "log_refund"; otherwise "end".
    """
    decision = state.get("human_decision")
    checkpoint = state.get("hitl_checkpoint")

    if decision != "approved":
        return "end"

    # Approved → move forward in flow
    if checkpoint == "eligibility":
        return "refund"
    if checkpoint == "refund":
        return "log_refund"

    return "end"
    

def build_insurance_cancellation_graph(llm_model: str, prompt_config: Dict[str, Any]) -> StateGraph:
    """
    Build and compile the insurance cancellation StateGraph with all nodes and edges.

    Args:
        llm_model: Model name for get_llm (used by intake and summary nodes).
        prompt_config: Dict with keys intake_assistant_prompt, summary_assistant_prompt (for prompt_builder).

    Returns:
        Compiled StateGraph with MemorySaver checkpointer (required for HITL interrupt/resume).
    """
    # Create the graph
    graph = StateGraph(InsuranceCancellationState)

    #Add the nodes
    intake_node = make_intake_agent_node(llm_model, prompt_config["intake_assistant_prompt"])
    analysis_node = make_analysis_agent_node()
    eligibility_hitl_node = make_hitl_node("eligibility")
    refund_node = make_refund_agent_node()
    refund_hitl_node = make_hitl_node("refund")
    logger_node = make_logger_agent_node()
    summary_node = make_summary_agent_node(llm_model, prompt_config["summary_assistant_prompt"])

    graph.add_node("intake", intake_node)
    graph.add_node("analysis", analysis_node)
    graph.add_node("eligibility_hitl", eligibility_hitl_node)
    graph.add_node("refund", refund_node)
    graph.add_node("refund_hitl", refund_hitl_node)
    graph.add_node("logger", logger_node)
    graph.add_node("summary", summary_node)

    #Add the edges
    graph.add_edge(START, "intake")
    #Intake routes
    graph.add_conditional_edges(
        "intake",
        route_from_intake,
        {
            "intake": "intake",
            "analysis": "analysis",
            "end": END,
        },
    )

    #Analysis routes -> eligibility HITL
    graph.add_conditional_edges(
        "analysis",
        route_from_analysis,
        {
            "eligibility_hitl": "eligibility_hitl",
            "end": END,
        },
    )

    #Eligibility HITL routes -> Refund or End
    graph.add_conditional_edges(
        "eligibility_hitl",
        route_after_human,
        {
            "refund": "refund",
            "end": END,
        },
    )

    #Refund routes -> refund HITL
    graph.add_conditional_edges(
        "refund",
        route_from_refund,
        {
            "refund_hitl": "refund_hitl",
            "end": END,
        },
    )

    #Refund HITL routes -> Log refund (after approval) or End
    graph.add_conditional_edges(
        "refund_hitl",
        route_after_human,
        {
            "logger": "logger",
            "end": END,
        },
    )

    graph.add_edge("logger", "summary")

    #Summary routes -> End
    graph.add_edge("summary", END)

    # Checkpointer required for interrupt/resume and update_state (human-in-the-loop)
    return graph.compile(checkpointer=MemorySaver())