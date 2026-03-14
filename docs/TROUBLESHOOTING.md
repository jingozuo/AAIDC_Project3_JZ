# Troubleshooting Guide

This guide helps you diagnose and fix common issues when running the Insurance Cancellation workflow (CLI, Streamlit, or tests).

## Quick diagnostics

Run the health check from the project root to verify config, data, directories, and optional LLM connectivity:

```bash
python -c "from codes.health import run_health_checks; run_health_checks(verbose=True)"
```

Or use the CLI entrypoint if available:

```bash
python3 codes/main.py --health
```
(or `python codes/main.py --health` if `python` points to Python 3)

---

## Common errors and fixes

### Configuration errors

| Symptom | Cause | Fix |
|--------|--------|-----|
| `ConfigError: Config file not found: ...` | Missing or wrong path to `config/config.yaml` or `config/prompt_config.yaml` | Run from **project root**; ensure `config/config.yaml` and `config/prompt_config.yaml` exist. |
| `ConfigError: Invalid YAML in ...` | Syntax error in a YAML file | Open the file, fix indentation or colons; use a YAML validator if needed. |
| `ConfigError: Config file is empty` | YAML file is empty or only comments | Add at least `llm_model: <model-name>` in `config/config.yaml` and required keys in `prompt_config.yaml`. |
| `Failed to initialize LLM` / `Unknown model name` | Wrong `llm_model` or missing API key | Set `llm_model` in `config/config.yaml` to one of: `gpt-4o-mini`, `llama-3.3-70b-versatile`, `gemini-2.5-flash`. Set the matching env var: `OPENAI_API_KEY`, `GROQ_API_KEY`, or `GOOGLE_API_KEY` in `.env`. |

### Data and paths

| Symptom | Cause | Fix |
|--------|--------|-----|
| `ConfigError: Data file not found: ...` | `data/insurance_policies.csv` missing | Create `data/` and add `insurance_policies.csv` with expected columns (see `codes/tools/data_lookup.py` CSV_KEY_MAP). |
| Policy lookup always returns "not found" | Wrong policy number or CSV format | Ensure CSV has a `Policy_Number` column; policy numbers are matched as stored (caller often normalizes with `.strip().upper()`). Check `data/insurance_policies.csv` content. |
| `ModuleNotFoundError: No module named 'codes'` | Running from wrong directory or wrong command | Run from **project root** (e.g. `python codes/main.py` or `streamlit run codes/streamlit_app.py`). Do not run as `python main.py` from inside `codes/` unless the project root is on `sys.path`. |

### LLM and API

| Symptom | Cause | Fix |
|--------|--------|-----|
| LLM call hangs or times out | Network or API latency; no timeout set | Set `request_timeout` in `config/config.yaml` (seconds). Increase retries/backoff or check network. |
| 401 / 403 from API | Invalid or missing API key | Copy `.env.example` to `.env` and set the correct key for your provider. |
| Rate limit (429) | Too many requests | Retries use exponential backoff; if persistent, reduce concurrency or switch provider/model. |

### Workflow and graph

| Symptom | Cause | Fix |
|--------|--------|-----|
| Graph stops with "recursion limit" | Too many steps (e.g. intake loops) | Increase `recursion_limit` in the config passed to `graph.invoke` (default 50). Check for infinite loop in node logic. |
| Streamlit: "missing ScriptRunContext" or session errors | Running Streamlit code outside Streamlit | Use `streamlit run codes/streamlit_app.py` from project root; do not run `streamlit_app.py` with plain `python`. |
| HITL: no prompt in CLI | Interrupt payload not recognized | Ensure you use a supported flow: intake (policy/confirm) or HITL (eligibility/refund). Check `main.py` interrupt handling. |

### Logs and outputs

| Symptom | Cause | Fix |
|--------|--------|-----|
| No `logs/guardrails_compliance.jsonl` | Logging not triggered or path not writable | Ensure `logs/` exists or is creatable; run a flow that triggers retries or validation (e.g. invalid policy, LLM failure). |
| No `outputs/insurance_cancellation_graph.png` | Visualization failed (API or PYPPETEER) | Check `outputs/` is writable; see console for "Could not save graph visualization". Mermaid `.mmd` may still be written. |
| PDF not generated | Notice generator failed after retries | Check `logs/guardrails_compliance.jsonl` for `error_handling` / `retry_exhausted` for `notice_generator`; ensure outputs dir is writable. |

---

## Log files and where to look

| File | Purpose |
|-----|--------|
| `logs/guardrails_compliance.jsonl` | Retries (`retry_attempt`, `retry_exhausted`), tool failures (`tool_failure`), error handling (`error_handling`), output filter events (`output_filter`). One JSON object per line. |
| Console (CLI) | High-level progress and error messages (e.g. "Configuration error", "Graph error"). |
| Streamlit UI | Errors shown in red (`st.error`); init errors before graph load. |

Search the compliance log for a given operation, e.g.:

```bash
grep '"operation":"data_lookup"' logs/guardrails_compliance.jsonl
grep '"event_type":"retry_exhausted"' logs/guardrails_compliance.jsonl
```

---

## Health checks

The `codes.health` module provides:

- **Config**: `config/config.yaml` and `config/prompt_config.yaml` exist and are valid YAML with required keys.
- **Data**: `data/insurance_policies.csv` exists and is readable.
- **Directories**: `outputs/` and `logs/` exist or can be created and written to.
- **LLM (optional)**: A single short LLM call with timeout to verify API key and connectivity.

Run all checks (optional LLM only if API key is set):

```python
from codes.health import run_health_checks
results = run_health_checks(verbose=True)
# If all passed: results["ok"] is True
```

Use this in CI or before starting the app to fail fast with clear messages.

---

## Timeouts and limits

| Setting | Where | Default | Description |
|--------|--------|--------|-------------|
| `request_timeout` | `config/config.yaml` | (none) | LLM HTTP request timeout in seconds. Prevents indefinite hangs. |
| `recursion_limit` | main/streamlit `config` for `graph.invoke` | 50 | Max graph steps per run. Increase if workflow is long. |
| Retry `max_attempts` | `codes/retry_logging.py` | 3 | Attempts for tool/LLM calls before failing. |
| Retry `timeout_seconds` | `call_with_retry(..., timeout_seconds=30)` | None | Per-call timeout for the wrapped function (if set). |

---

## Running tests

- Run from **project root**: `pytest tests/ -v` or `python3 tests/run_tests.py`.
- If tests fail with `ModuleNotFoundError: No module named 'codes'`, ensure you are in the project root and that `tests/conftest.py` adds the root to `sys.path`.
- Typer deprecation warnings from DeepEval are filtered in `conftest.py`; safe to ignore.
- E2E tests use mocked LLM and may create temp files in `outputs/` and `logs/`; they clean up or use temp dirs where possible.

---

## Getting help

1. Run `run_health_checks(verbose=True)` and fix any reported failures.
2. Check `logs/guardrails_compliance.jsonl` for the last few events.
3. Confirm you are on project root, correct `.env`, and correct `config/config.yaml` and `config/prompt_config.yaml`.
4. For API issues, verify the API key and `request_timeout`; try a minimal LLM call outside the app.
