"""
Project paths and layout — single source of truth for filesystem paths.

This module defines all directories and file paths used by the multi-agent
insurance cancellation workflow. Import paths from here only; do not construct
paths manually in other modules so that:
  - Paths stay consistent across agents and tools.
  - Changing layout (e.g. moving data/ or config/) requires edits in one place.
  - Responsibilities are clear: data tools use DATA_*, output tools use OUTPUTS_*,
    and config consumers use CONFIG_*.

Usage by component:
  - Data tools (data_lookup): DATA_DIR, DATA_FILE_PATH
  - Output tools (refund_logger, notice_generator): OUTPUTS_DIR
  - Config (main, prompt_builder, graph): CONFIG_DIR, CONFIG_FILE_PATH,
    PROMPT_CONFIG_FILE_PATH

Adding new paths:
  1. Define the constant in the appropriate section (Outputs / Data / Config).
  2. Use os.path.join(ROOT_DIR, ...) or join from an existing dir (e.g. DATA_DIR).
  3. Document which agent or tool uses it in the section comment and in this docstring.

File location: This file lives in code/paths.py. ROOT_DIR is the project root (parent of code/).
"""
import os

# Project root: directory containing the "code" package (parent of this file's dir).
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Outputs (refund_logger, notice_generator) ---
# Directory where generated refund logs and PDF notices are written. Create if missing.
OUTPUTS_DIR = os.path.join(ROOT_DIR, "outputs")
# Compliance and safety logging (guardrails_safety).
LOGS_DIR = os.path.join(ROOT_DIR, "logs")
COMPLIANCE_LOG_PATH = os.path.join(LOGS_DIR, "guardrails_compliance.jsonl")

# --- Data (data_lookup only; single source for policy data) ---
# Directory containing CSV and other data files. Do not hardcode other data paths elsewhere.
DATA_DIR = os.path.join(ROOT_DIR, "data")
# Canonical path to the insurance policies CSV used by the data lookup tool.
DATA_FILE_PATH = os.path.join(DATA_DIR, "insurance_policies.csv")

# --- Config (main, prompt_builder, graph) ---
# Directory for YAML config and prompt templates.
CONFIG_DIR = os.path.join(ROOT_DIR, "config")
# Main app/config YAML (e.g. llm_model, graph options).
CONFIG_FILE_PATH = os.path.join(CONFIG_DIR, "config.yaml")
# Prompt templates and agent instructions (e.g. system prompts per role).
PROMPT_CONFIG_FILE_PATH = os.path.join(CONFIG_DIR, "prompt_config.yaml")