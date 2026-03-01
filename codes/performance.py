"""
System performance and evaluation — DeepEval test-case evaluation.

  - run_evaluation(samples): DeepEval evaluation for eligibility correctness, refund
    correctness, workflow sequencing, summary notice quality, agent boundary enforcement.
"""
import os
import time
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# DeepEval evaluation (five dimensions)
# ---------------------------------------------------------------------------

def run_evaluation(
    samples: List[Dict[str, Any]],
    llm_model: str = "llama-3.3-70b-versatile",
) -> Dict[str, Any]:
    """
    Run DeepEval test cases for: eligibility correctness, refund correctness,
    workflow sequencing, summary notice quality, agent boundary enforcement.

    Delegates to evaluation.run_evaluation. Each sample may include policy_details,
    output, notice_text, node_sequence, tool_usage_trace (see evaluation.EvaluationSample).
    """
    try:
        from evaluation import run_evaluation as _run
    except ImportError:
        from code.evaluation import run_evaluation as _run
    return _run(samples=samples, llm_model=llm_model)
