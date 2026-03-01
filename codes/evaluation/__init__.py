"""
System evaluation using DeepEval.

Evaluates test cases on five dimensions:
  1. Eligibility correctness
  2. Refund calculation correctness
  3. Workflow sequencing
  4. Summary notice quality
  5. Agent boundary enforcement

Use run_evaluation(samples, llm_model=...) to run all five dimensions. Each sample may include
policy_details, output, notice_text, node_sequence, tool_usage_trace (see deepeval_eval.py).
"""
from typing import Any, Dict, List, Optional, TypedDict

from .deepeval_eval import run_evaluation as deepeval_run_evaluation
from .deepeval_eval import (
    EXPECTED_NODE_SEQUENCE,
    ALLOWED_TOOLS_BY_NODE,
)


class EvaluationSample(TypedDict, total=False):
    """Single test case for DeepEval. All fields optional; include what each dimension needs."""
    policy_details: Dict[str, Any]
    output: str
    notice_text: str
    user_input: str
    eligibility_decision: str
    node_sequence: List[str]
    tool_usage_trace: List[Dict[str, Any]]
    tool_usage_trace_str: str


def run_evaluation(
    samples: List[EvaluationSample],
    llm_model: str = "llama-3.3-70b-versatile",
) -> Dict[str, Any]:
    """
    Run DeepEval on test cases for the five dimensions.

    Args:
        samples: List of evaluation samples (policy_details, output, notice_text,
                 node_sequence, tool_usage_trace as needed).
        llm_model: Model name for DeepEval GEval (e.g. llama-3.3-70b-versatile).

    Returns:
        Dict with eligibility_correctness, refund_correctness, workflow_sequencing,
        summary_notice_quality, agent_boundary_enforcement, overall, per_sample.
    """
    return deepeval_run_evaluation(samples=samples, llm_model=llm_model)


__all__ = [
    "run_evaluation",
    "EvaluationSample",
    "EXPECTED_NODE_SEQUENCE",
    "ALLOWED_TOOLS_BY_NODE",
]
