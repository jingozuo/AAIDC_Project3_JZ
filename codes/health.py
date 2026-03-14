"""
Health checks for the insurance cancellation workflow.

Run before starting the app or in CI to verify config, data, directories,
and optional LLM connectivity. Use run_health_checks() for a single entry point.
"""
import os
from typing import Any, Dict, List

from codes.paths import (
    CONFIG_FILE_PATH,
    PROMPT_CONFIG_FILE_PATH,
    DATA_FILE_PATH,
    OUTPUTS_DIR,
    LOGS_DIR,
)


def _check_config(verbose: bool = False) -> Dict[str, Any]:
    """Verify config and prompt_config YAML files exist and are valid."""
    result: Dict[str, Any] = {"name": "config", "ok": False, "message": ""}
    try:
        from codes.utils import load_config, ConfigError
    except ImportError:
        result["message"] = "Cannot import codes.utils"
        return result
    for path, label in [(CONFIG_FILE_PATH, "config"), (PROMPT_CONFIG_FILE_PATH, "prompt_config")]:
        try:
            data = load_config(path)
            if not isinstance(data, dict):
                result["message"] = f"{label} is not a YAML object"
                return result
            if path == CONFIG_FILE_PATH and "llm_model" not in data:
                result["message"] = "config.yaml must contain llm_model"
                return result
            if path == PROMPT_CONFIG_FILE_PATH:
                if "intake_assistant_prompt" not in data or "summary_assistant_prompt" not in data:
                    result["message"] = "prompt_config.yaml must contain intake_assistant_prompt and summary_assistant_prompt"
                    return result
            if verbose:
                result.setdefault("details", []).append(f"{label}: ok")
        except Exception as e:
            result["message"] = f"{label} ({path}): {e}"
            return result
    result["ok"] = True
    result["message"] = "Config files valid"
    return result


def _check_data(verbose: bool = False) -> Dict[str, Any]:
    """Verify data file exists and is readable."""
    result: Dict[str, Any] = {"name": "data", "ok": False, "message": ""}
    if not os.path.isfile(DATA_FILE_PATH):
        result["message"] = f"Data file not found: {DATA_FILE_PATH}"
        return result
    try:
        with open(DATA_FILE_PATH, "r", encoding="utf-8") as f:
            f.read()
    except OSError as e:
        result["message"] = f"Cannot read data file: {e}"
        return result
    result["ok"] = True
    result["message"] = "Data file readable"
    return result


def _check_directories(verbose: bool = False) -> Dict[str, Any]:
    """Verify outputs and logs dirs exist or can be created and written to."""
    result: Dict[str, Any] = {"name": "directories", "ok": False, "message": ""}
    for dir_path, label in [(OUTPUTS_DIR, "outputs"), (LOGS_DIR, "logs")]:
        if not os.path.isdir(dir_path):
            try:
                os.makedirs(dir_path, exist_ok=True)
            except OSError as e:
                result["message"] = f"Cannot create {label} dir {dir_path}: {e}"
                return result
        probe = os.path.join(dir_path, ".health_probe")
        try:
            with open(probe, "w") as f:
                f.write("")
            os.remove(probe)
        except OSError as e:
            result["message"] = f"Cannot write to {label} dir: {e}"
            return result
        if verbose:
            result.setdefault("details", []).append(f"{label}: ok")
    result["ok"] = True
    result["message"] = "Outputs and logs directories writable"
    return result


def _check_llm(timeout_seconds: float = 10.0, verbose: bool = False) -> Dict[str, Any]:
    """
    Optionally verify LLM connectivity with a short prompt.
    Skips (ok=True) if config or LLM init fails so CI without API key still passes other checks.
    """
    result: Dict[str, Any] = {"name": "llm", "ok": False, "message": "", "skipped": False}
    try:
        from codes.utils import load_config, ConfigError
        from codes.llm import get_llm
    except ImportError as e:
        result["skipped"] = True
        result["message"] = f"Cannot import: {e}"
        result["ok"] = True
        return result
    try:
        config = load_config(CONFIG_FILE_PATH)
        model_name = config.get("llm_model")
        if not model_name:
            result["skipped"] = True
            result["message"] = "No llm_model in config"
            result["ok"] = True
            return result
        request_timeout = config.get("request_timeout")
        if request_timeout is not None:
            timeout_seconds = min(float(request_timeout), timeout_seconds)
        llm = get_llm(model_name, 0.0, request_timeout=timeout_seconds)
        from langchain_core.messages import HumanMessage
        llm.invoke([HumanMessage(content="Say OK")])
        result["ok"] = True
        result["message"] = "LLM responded"
    except Exception as e:
        result["message"] = str(e)
        result["ok"] = False
    return result


def run_health_checks(
    *,
    skip_llm: bool = False,
    llm_timeout: float = 10.0,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Run all health checks and return a summary.

    Args:
        skip_llm: If True, do not run the LLM connectivity check (e.g. in CI without API key).
        llm_timeout: Timeout in seconds for the LLM ping when skip_llm is False.
        verbose: If True, add per-check details to results.

    Returns:
        Dict with:
          - ok: True if all non-skipped checks passed.
          - results: List of per-check dicts (name, ok, message, optional details/skipped).
    """
    results: List[Dict[str, Any]] = []
    for check_fn in [_check_config, _check_data, _check_directories]:
        results.append(check_fn(verbose=verbose))
    if not skip_llm:
        results.append(_check_llm(timeout_seconds=llm_timeout, verbose=verbose))
    else:
        results.append({"name": "llm", "ok": True, "message": "skipped", "skipped": True})

    failed = [r for r in results if not r["ok"]]
    return {
        "ok": len(failed) == 0,
        "results": results,
    }
