# AAIDC Project 3 - Agentic AI In Production Program for Insurance Cancellation

A multi-agent workflow built with **LangGraph** that guides users through policy lookup, eligibility analysis, refund calculation, and cancellation notice generation—with **human-in-the-loop (HITL)** approval at eligibility and refund stages.

## Features

- **Multi-step graph**: Intake → Analysis → Eligibility HITL → Refund → Refund HITL → Log refund → Summary
- **Human-in-the-loop**: Pauses for human approval after eligibility check and after refund calculation; supports resume via `update_state`
- **Refund logging only after approval**: Refund records are written to `outputs/refund_log.csv` only when the human approves the refund (not before)
- **Configurable LLM**: Supports Groq, OpenAI, or Google (set API key and model in config)
- **PDF notices**: Generates cancellation notices in `outputs/`
- **Retry with exponential backoff**: Tool and LLM calls (data lookup, refund logger, notice generator, LLM invoke) use `codes/retry_logging.py` — up to 3 attempts with exponential backoff; failures are logged
- **Structured logging**: Failures, retries, and fallback events are written to `logs/guardrails_compliance.jsonl` (event types: `retry_attempt`, `retry_exhausted`, `tool_failure`, `error_handling`, `output_filter`, input validation) for debugging and traceability

## Workflow (Graph)

```
START → intake (loop until policy confirmed)
     → analysis (lookup policy, check eligibility)
     → eligibility_hitl (HITL: approve/reject eligibility)
     → refund (calculate refund amount; no logging yet)
     → refund_hitl (HITL: approve/reject refund)
     → logger (log to CSV only if approved)
     → summary (generate PDF notice)
     → END
```

- **Reject** at either HITL → flow ends (no refund log, no summary).
- **Approve** at eligibility HITL → proceeds to refund calculation; **approve** at refund HITL → log refund, then generate summary/PDF.

## Project Structure

```
AAIDC_Project3_JZ/
├── codes/
│   ├── main.py             # Entry point; runs graph, handles interrupts and HITL resume
│   ├── streamlit_app.py    # Streamlit UI for the same workflow
│   ├── graph.py            # LangGraph definition (nodes, edges, routing)
│   ├── nodes.py            # Node implementations (intake, analysis, refund, HITL, logger, summary)
│   ├── state.py            # InsuranceCancellationState and Phase types
│   ├── hitl_cli.py         # CLI for human review (approve/reject)
│   ├── llm.py              # LLM initialization (Groq/OpenAI/Google)
│   ├── paths.py            # Paths for config, data, outputs (single source; see docstring)
│   ├── agent_roles.py      # Agent and tool role definitions (responsibilities, inputs/outputs)
│   ├── guardrails_safety.py # Input/output validation, compliance logging (logs/guardrails_compliance.jsonl)
│   ├── retry_logging.py    # Retry with exponential backoff + compliance log for tool/LLM failures
│   ├── performance.py      # Run metrics + DeepEval evaluation (5 dimensions)
│   ├── evaluation/         # DeepEval test cases (eligibility, refund, sequencing, notice, boundary)
│   ├── prompt_builder.py   # Prompt construction from config
│   ├── output_graph.py     # Graph visualization export
│   └── tools/
│       ├── data_lookup.py        # Policy lookup (e.g. insurance_policies.csv)
│       ├── cancellation_rules.py # Eligibility rules
│       ├── refund_calculator.py  # Refund amount calculation
│       ├── refund_logger.py      # Write refund records to CSV
│       └── notice_generator.py   # Generate PDF cancellation notices
├── config/
│   ├── config.yaml         # LLM model name
│   └── prompt_config.yaml  # Prompts for intake/summary
├── data/
│   └── insurance_policies.csv  # Policy data (path in codes/paths.py)
├── docs/                   # e.g. RETRY_AND_LOGGING_ANALYSIS.md
├── logs/                   # guardrails_compliance.jsonl (retry, failures, validation events)
├── outputs/                # refund_log.csv, generated PDFs, insurance_cancellation_graph.png
├── tests/                  # pytest unit and integration tests
├── requirements.txt
├── .env.example            # API keys (GROQ_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY)
└── README.md
```

## Setup

1. **Clone and install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Environment**

   Copy `.env.example` to `.env` and set one of:

   - `GROQ_API_KEY` (e.g. for `llama-3.3-70b-versatile`)
   - `OPENAI_API_KEY`
   - `GOOGLE_API_KEY`

3. **Config**

   In `config/config.yaml` set the `llm_model` to match your provider (e.g. `llama-3.3-70b-versatile` for Groq).

4. **Data**

   Use insurance_policies.csv file to store some mock test data.
   Ensure `data/insurance_policies.csv` exists (see `codes/paths.py` for `DATA_FILE_PATH`).

## Run

From the project root:

```bash
python codes/main.py
```

Or from the `codes` directory:

```bash
cd codes && python main.py
```

When the graph pauses at a HITL step, the CLI will prompt:

- `[A] Approve` / `[R] Reject`

### Streamlit UI

Run the same workflow in a browser:

```bash
streamlit run codes/streamlit_app.py
```

Run from the **project root** so the `codes` package is found. The UI handles policy number entry, policy confirmation (yes/no), and HITL approve/reject with buttons. Use **New session** in the sidebar to start over.

## Tests

Unit and integration tests use **pytest**. Run from the project root:

```bash
pytest tests/ -v
```

Or use the runner script (run it with **Python**, not pytest):

```bash
python3 tests/run_tests.py -v
```

**Note:** Run a single test, e.g. test_e2e_system_flows.py

```bash
pytest tests/test_e2e_system_flows.py
```

## Retry and logging

- **Retry**: Tool and LLM calls are wrapped with `call_with_retry` (in `codes/retry_logging.py`): up to **3 attempts** with **exponential backoff** (base 1s, max 60s). Used for: policy lookup (`data_lookup`), refund logging (`refund_logger`), notice PDF generation (`notice_generator`), and summary LLM invoke.
- **Logging**: All retry attempts and final failures are written to **`logs/guardrails_compliance.jsonl`** (same file as guardrails validation events). Event types:
  - `retry_attempt` — a retry is about to happen (includes attempt, max_attempts, wait_seconds, error snippet).
  - `retry_exhausted` — the call failed after all attempts (includes operation name, error, args_preview).
  - `tool_failure` — e.g. policy lookup failed after retries (intake treats as “policy not found”).
  - `error_handling` — e.g. LLM or PDF failure after retries; fallback notice or `[PDF generation failed]` used.
- **Traceability**: Each log line is JSON with `timestamp`, `event_type`, `stage`, `message`, and optional `error`, `metadata`. See `docs/RETRY_AND_LOGGING_ANALYSIS.md` for details.

## Outputs

- **`outputs/refund_log.csv`** — Only after human **approves** the refund step, new Refund records are logged in refund_log.csv file. This file is generated once the first refund record is logged in.
- **`outputs/Cancellation_Notice_<policy>.pdf`** — Generated only when the workflow completes (after refund approval and logger).
- **`outputs/insurance_cancellation_graph.png`** — Generated once when the workflow finishes.

## State and Phases

Key state fields (see `state.py`): `phase`, `policy_details`, `messages`, `output`, `human_decision`, `hitl_checkpoint`. Phases drive routing (e.g. `human_eligibility_check` → eligibility HITL, `human_refund_check` → refund HITL, then `ready_for_summary` after refund approval).

## Agent and tool roles

Each graph node and each tool has a single, documented responsibility (see `codes/agent_roles.py`):

- **Agents**: Intake (collect & confirm policy), Analysis (eligibility only), Refund (compute amount; no logging), Eligibility/Refund HITL, Logger (persist after approval), Summary (notice + PDF).
- **Tools**: Data Lookup (Intake only; uses `paths.DATA_FILE_PATH`), Cancellation Rules (Analysis + Refund), Refund Calculator (Refund only; no I/O), Refund Logger (Log Refund only), Notice Generator (Summary only).

`paths.py` is the single source for filesystem paths and documents which components use which paths. `refund_calculator.py` defines the input/output contract for refund computation so refund logic stays in one place.

## Health checks and troubleshooting

- **Health checks**: Run `python codes/main.py --health` (or `-H`) to verify config files, data file, and output/logs directories. LLM connectivity is skipped by default; see `codes.health.run_health_checks(skip_llm=False)` for an optional LLM ping.
- **Timeouts**: In `config/config.yaml` you can set `request_timeout` (seconds) for LLM HTTP requests to avoid indefinite hangs. Retry logic supports an optional `timeout_seconds` per call (see `codes/retry_logging.py`). Graph execution uses `recursion_limit` (default 50) in the invoke config.
- **Troubleshooting**: See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for common errors, log locations, and how to debug config, data, LLM, and workflow issues.

## Performance and evaluation

Evaluation uses **DeepEval** only, with test cases for five dimensions (see `codes/evaluation/deepeval_eval.py`):

1. **Eligibility correctness** — Workflow eligibility decision matches rules (active status, payment made, current date before end date).
2. **Refund calculation correctness** — Stated refund matches the formula: payment × (remaining_days / total_days).
3. **Workflow sequencing** — Node order is correct: intake → analysis → eligibility_hitl → refund → refund_hitl → logger → summary.
4. **Summary notice quality** — Notice is clear, complete, and correctly states policy number, refund, and cancellation.
5. **Agent boundary enforcement** — Each node used only its allowed tools (Intake: data_lookup; Analysis: cancellation_rules; Refund: cancellation_rules, refund_calculator; Logger: refund_logger; Summary: notice_generator).


## Visualize the graph

Use `output_graph.py` (e.g. from `codes/`) to export a visualization of the compiled graph if needed for debugging or documentation.
