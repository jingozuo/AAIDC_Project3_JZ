"""
DeepEval evaluation for the insurance cancellation workflow.

Evaluates five dimensions via GEval:
  1. Eligibility correctness
  2. Refund calculation correctness
  3. Workflow sequencing
  4. Summary notice quality
  5. Agent boundary enforcement

Use llama-3.3-70b-versatile (Groq) by default; set GROQ_API_KEY in .env.
Groq does not support logprobs, so we use a wrapper that omits them (see GroqLiteLLMModel).
"""
import os
from typing import Any, Dict, List, Optional, Tuple, Union

EXPECTED_NODE_SEQUENCE = [
    "intake", "analysis", "eligibility_hitl", "refund",
    "refund_hitl", "logger", "summary",
]

ALLOWED_TOOLS_BY_NODE: Dict[str, List[str]] = {
    "intake": ["data_lookup"],
    "analysis": ["cancellation_rules"],
    "eligibility_hitl": [],
    "refund": ["cancellation_rules", "refund_calculator"],
    "refund_hitl": [],
    "logger": ["refund_logger"],
    "summary": ["notice_generator"],
}


def import_deepeval():
    try:
        from deepeval.test_case import LLMTestCase, LLMTestCaseParams
        from deepeval.metrics import GEval
        return LLMTestCase, LLMTestCaseParams, GEval
    except ImportError as e:
        raise ImportError("Evaluation requires: pip install deepeval") from e


def get_groq_litellm_no_logprobs():
    """
    Return a LiteLLMModel subclass that omits logprobs in raw_response calls
    (Groq API does not support logprobs). GEval then uses the JSON score from the reply.
    """
    from deepeval.models import LiteLLMModel
    from deepeval.models.utils import require_secret_api_key

    class GroqLiteLLMModel(LiteLLMModel):
        def generate_raw_response(self, prompt: str, top_logprobs: int = 5) -> Tuple[Any, float]:
            from litellm import completion
            api_key = require_secret_api_key(
                self.api_key,
                provider_label="LiteLLM",
                env_var_name="LITELLM_API_KEY|OPENAI_API_KEY|GROQ_API_KEY",
                param_hint="api_key",
            )
            content = [{"type": "text", "text": prompt}]
            params = {
                "model": self.name,
                "messages": [{"role": "user", "content": content}],
                "temperature": self.temperature,
                "api_key": api_key,
            }
            if self.base_url:
                params["api_base"] = self.base_url
            # Do NOT pass logprobs/top_logprobs — Groq does not support them
            response = completion(**params)
            cost = self.calculate_cost(response)
            return response, float(cost)

        async def a_generate_raw_response(self, prompt: str, top_logprobs: int = 5) -> Tuple[Any, float]:
            from litellm import acompletion
            api_key = require_secret_api_key(
                self.api_key,
                provider_label="LiteLLM",
                env_var_name="LITELLM_API_KEY|OPENAI_API_KEY|GROQ_API_KEY",
                param_hint="api_key",
            )
            content = [{"type": "text", "text": prompt}]
            params = {
                "model": self.name,
                "messages": [{"role": "user", "content": content}],
                "temperature": self.temperature,
                "api_key": api_key,
            }
            if self.base_url:
                params["api_base"] = self.base_url
            response = await acompletion(**params)
            cost = self.calculate_cost(response)
            return response, float(cost)

    return GroqLiteLLMModel


def get_geval_model(llm_model: str) -> Union[str, Any]:
    """
    Return the model to pass to GEval: Groq LiteLLM subclass that does not
    request logprobs (llama-3.3-70b-versatile), or the string for OpenAI.
    """
    if llm_model == "llama-3.3-70b-versatile":
        api_key = os.environ.get("GROQ_API_KEY")
        GroqLiteLLM = get_groq_litellm_no_logprobs()
        return GroqLiteLLM(
            model="groq/llama-3.3-70b-versatile",
            api_key=api_key,
            temperature=0.0,
        )
    return llm_model


def build_eligibility_test(sample: Dict[str, Any], LLMTestCaseCls) -> Any:
    policy = sample.get("policy_details") or {}
    actual = sample.get("output") or sample.get("eligibility_decision") or "No eligibility output."
    context = (
        f"Policy status: {policy.get('policy_status')}. Payment made: {policy.get('is_payment_made')}. "
        f"Start date: {policy.get('start_date')}. End date: {policy.get('end_date')}. "
        "Eligibility rules: policy must be Active, payment made, and current date before end date."
    )
    return LLMTestCaseCls(
        input="Evaluate eligibility correctness.",
        actual_output=actual,
        context=[context],
        expected_output="Eligible if status=Active, payment made=True, and current date before end_date; otherwise not eligible.",
    )


def build_refund_test(sample: Dict[str, Any], LLMTestCaseCls) -> Any:
    policy = sample.get("policy_details") or {}
    actual = (
        f"Refund amount: {policy.get('refund_amount')}. Reason: {policy.get('refund_reason', '')}. "
        f"Output: {sample.get('output', '')}"
    )
    context = (
        f"Policy start_date: {policy.get('start_date')}, end_date: {policy.get('end_date')}, "
        f"payment_amount: {policy.get('payment_amount')}. "
        "Correct formula: refund = payment_amount * (remaining_days / total_days), rounded to 2 decimals."
    )
    return LLMTestCaseCls(
        input="Evaluate refund calculation correctness.",
        actual_output=actual,
        context=[context],
        expected_output="The stated refund amount must match the proportional formula from dates and payment.",
    )


def build_sequencing_test(sample: Dict[str, Any], LLMTestCaseCls) -> Any:
    actual_sequence = sample.get("node_sequence") or []
    actual_str = " -> ".join(str(n) for n in actual_sequence) if actual_sequence else "No sequence recorded."
    expected_str = " -> ".join(EXPECTED_NODE_SEQUENCE)
    context = (
        f"Expected order (main path): {expected_str}. "
        "Intake may repeat. Check: intake then analysis then eligibility_hitl then refund then refund_hitl then logger then summary."
    )
    return LLMTestCaseCls(
        input="Evaluate workflow sequencing.",
        actual_output=actual_str,
        context=[context],
        expected_output=expected_str,
    )


def build_notice_quality_test(sample: Dict[str, Any], LLMTestCaseCls) -> Any:
    policy = sample.get("policy_details") or {}
    notice = sample.get("notice_text") or sample.get("output") or ""
    context = (
        f"Policy number: {policy.get('policy_number')}. "
        f"Customer: {policy.get('first_name')} {policy.get('last_name')}. "
        f"Refund amount: {policy.get('refund_amount')}. Refund reason: {policy.get('refund_reason', '')}."
    )
    return LLMTestCaseCls(
        input="Evaluate summary notice quality.",
        actual_output=notice,
        context=[context],
        expected_output="Notice should be clear, professional, include policy number, customer reference, refund amount, and confirm cancellation.",
    )


def build_boundary_test(sample: Dict[str, Any], LLMTestCaseCls) -> Any:
    trace = sample.get("tool_usage_trace") or []
    if trace:
        actual_str = "\n".join(f"{t.get('node', '')}: used tools {t.get('tools', [])}" for t in trace)
    else:
        actual_str = sample.get("tool_usage_trace_str") or "No tool usage trace."
    allowed_str = "\n".join(f"{node}: {tools}" for node, tools in ALLOWED_TOOLS_BY_NODE.items())
    context = (
        f"Allowed tools per node:\n{allowed_str}. "
        "Each node must use ONLY these tools; no other tools."
    )
    return LLMTestCaseCls(
        input="Evaluate agent boundary enforcement.",
        actual_output=actual_str,
        context=[context],
        expected_output="Each node must use only the tools listed for that node.",
    )


def run_evaluation(
    samples: List[Dict[str, Any]],
    llm_model: str = "llama-3.3-70b-versatile",
) -> Dict[str, Any]:
    """
    Run DeepEval GEval for the five dimensions. Uses Groq (llama-3.3-70b-versatile)
    when llm_model is llama-3.3-70b-versatile (set GROQ_API_KEY). For OpenAI, pass
    llm_model e.g. gpt-4o-mini and set OPENAI_API_KEY.
    """
    LLMTestCaseCls, LLMTestCaseParams, GEvalCls = import_deepeval()
    eval_model = get_geval_model(llm_model)

    if not samples:
        return {
            "eligibility_correctness": 0.0, "refund_correctness": 0.0,
            "workflow_sequencing": 0.0, "summary_notice_quality": 0.0,
            "agent_boundary_enforcement": 0.0, "overall": 0.0, "per_sample": [],
        }

    metrics = [
        ("eligibility_correctness", GEvalCls(
            name="EligibilityCorrectness",
            criteria="Does the actual_output show the correct eligibility decision given the context? Eligible only if policy status is Active, payment made, and current date before end date. Return 1 if correct, 0 if wrong.",
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.CONTEXT],
            threshold=0.5, strict_mode=True, model=eval_model,
        )),
        ("refund_correctness", GEvalCls(
            name="RefundCorrectness",
            criteria="Given the context (dates, payment), does the actual_output state a refund amount correct under: refund = payment * (remaining_days / total_days)? Return 1 if correct or very close, 0 if wrong.",
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.CONTEXT],
            threshold=0.5, strict_mode=True, model=eval_model,
        )),
        ("workflow_sequencing", GEvalCls(
            name="WorkflowSequencing",
            criteria="Does the actual_output node sequence follow: intake, analysis, eligibility_hitl, refund, refund_hitl, logger, summary? Allow intake to repeat. Return 1 if correct, 0 if not.",
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.CONTEXT],
            threshold=0.5, strict_mode=True, model=eval_model,
        )),
        ("summary_notice_quality", GEvalCls(
            name="SummaryNoticeQuality",
            criteria="Is the actual_output (notice) clear, professional, and include policy number, customer/refund info, and cancellation confirmation? Return 1 if yes, 0 if not.",
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.CONTEXT],
            threshold=0.5, strict_mode=True, model=eval_model,
        )),
        ("agent_boundary_enforcement", GEvalCls(
            name="AgentBoundaryEnforcement",
            criteria="Given allowed tools per node in context, did each node in actual_output use only its allowed tools? Return 1 if yes, 0 if any used a tool not in its list.",
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.CONTEXT],
            threshold=0.5, strict_mode=True, model=eval_model,
        )),
    ]

    dim_scores: Dict[str, List[float]] = {name: [] for name, _ in metrics}
    per_sample: List[Dict[str, Any]] = []

    for idx, sample in enumerate(samples):
        sample_result: Dict[str, Any] = {"index": idx}
        tests = [
            ("eligibility_correctness", build_eligibility_test(sample, LLMTestCaseCls)),
            ("refund_correctness", build_refund_test(sample, LLMTestCaseCls)),
            ("workflow_sequencing", build_sequencing_test(sample, LLMTestCaseCls)),
            ("summary_notice_quality", build_notice_quality_test(sample, LLMTestCaseCls)),
            ("agent_boundary_enforcement", build_boundary_test(sample, LLMTestCaseCls)),
        ]
        for dim_name, tc in tests:
            metric = next(m for n, m in metrics if n == dim_name)
            try:
                returned = metric.measure(tc)
                score = float(returned) if returned is not None else float(getattr(metric, "score", 0.0))
                score = max(0.0, min(1.0, score))
                dim_scores[dim_name].append(score)
                sample_result[dim_name] = score
                sample_result[f"{dim_name}_reason"] = getattr(metric, "reason", None)
            except Exception as e:
                dim_scores[dim_name].append(0.0)
                sample_result[dim_name] = 0.0
                sample_result[f"{dim_name}_error"] = str(e)
                sample_result[f"{dim_name}_reason"] = None
        per_sample.append(sample_result)

    n = len(samples)
    result = {
        "eligibility_correctness": sum(dim_scores["eligibility_correctness"]) / n if n else 0.0,
        "refund_correctness": sum(dim_scores["refund_correctness"]) / n if n else 0.0,
        "workflow_sequencing": sum(dim_scores["workflow_sequencing"]) / n if n else 0.0,
        "summary_notice_quality": sum(dim_scores["summary_notice_quality"]) / n if n else 0.0,
        "agent_boundary_enforcement": sum(dim_scores["agent_boundary_enforcement"]) / n if n else 0.0,
        "per_sample": per_sample,
    }
    scores_list = [result["eligibility_correctness"], result["refund_correctness"], result["workflow_sequencing"],
                   result["summary_notice_quality"], result["agent_boundary_enforcement"]]
    result["overall"] = sum(scores_list) / len(scores_list) if scores_list else 0.0
    return result
