"""
Run DeepEval evaluation (default: llama-3.3-70b-versatile via Groq).

Usage:
  python -m code.run_evaluation
  or from code/: python run_evaluation.py

Set GROQ_API_KEY in .env (or environment) for the default model.
Set EVAL_LLM_MODEL to override (e.g. EVAL_LLM_MODEL=gpt-4o-mini with OPENAI_API_KEY).
"""
import os
import sys

# Load .env so GROQ_API_KEY / OPENAI_API_KEY are available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_code_dir = os.path.dirname(os.path.abspath(__file__))
if _code_dir not in sys.path:
    sys.path.insert(0, _code_dir)
_root = os.path.dirname(_code_dir)
if _root not in sys.path:
    sys.path.insert(0, _root)

try:
    from performance import run_evaluation
except ImportError:
    from code.performance import run_evaluation

MOCK_SAMPLES = [
    {
        "policy_details": {
            "policy_number": "POL01212",
            "first_name": "John", "last_name": "Smith", "email": "j@e.com",
            "policy_status": "Active", "start_date": "2025-09-06", "end_date": "2026-09-06",
            "payment_amount": "600.0", "is_payment_made": True, "is_policy_found": True,
            "refund_amount": 500.0, "refund_reason": "Refund amount calculated successfully.",
        },
        "output": "Policy is eligible for cancellation. Refund Amount: $500.0.",
        "notice_text": "Cancellation notice for policy POL01212. Refund: $500.0.",
        "user_input": "POL01212",
        "node_sequence": ["intake", "intake", "analysis", "eligibility_hitl", "refund", "refund_hitl", "logger", "summary"],
        "tool_usage_trace": [
            {"node": "intake", "tools": ["data_lookup"]},
            {"node": "analysis", "tools": ["cancellation_rules"]},
            {"node": "refund", "tools": ["cancellation_rules", "refund_calculator"]},
            {"node": "logger", "tools": ["refund_logger"]},
            {"node": "summary", "tools": ["notice_generator"]},
        ],
    },
]


def main():
    llm_model = os.environ.get("EVAL_LLM_MODEL", "llama-3.3-70b-versatile")
    print("DeepEval (5 dimensions). Model:", llm_model)
    if llm_model == "llama-3.3-70b-versatile" and not os.environ.get("GROQ_API_KEY"):
        print("Warning: GROQ_API_KEY not set. Set it in .env or environment for Groq/Llama.")
    print()
    results = run_evaluation(MOCK_SAMPLES, llm_model=llm_model)
    print("Eligibility correctness:    ", results.get("eligibility_correctness"))
    print("Refund correctness:        ", results.get("refund_correctness"))
    print("Workflow sequencing:       ", results.get("workflow_sequencing"))
    print("Summary notice quality:    ", results.get("summary_notice_quality"))
    print("Agent boundary enforcement:", results.get("agent_boundary_enforcement"))
    print("Overall:                   ", results.get("overall"))
    print("Done.")


if __name__ == "__main__":
    main()
