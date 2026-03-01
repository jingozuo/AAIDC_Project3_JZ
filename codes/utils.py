"""
Utility functions for config and data loading.

Role: load_config reads a YAML file (default paths.CONFIG_FILE_PATH) and returns a dict.
load_csv reads a CSV file as raw text (default paths.DATA_FILE_PATH). Used by main and
other callers that need config or raw CSV content. For structured policy lookup, use
tools.data_lookup.lookup_policy_in_csv instead of load_csv.
"""
import yaml
import os
from typing import Any, Dict

from codes.paths import CONFIG_FILE_PATH, DATA_FILE_PATH, OUTPUTS_DIR
from codes.llm import get_llm


def load_config(config_path: str = CONFIG_FILE_PATH) -> Dict[str, Any]:
    """
    Load a YAML config file and return the parsed dict.

    Args:
        config_path: Path to the YAML file (default: CONFIG_FILE_PATH).

    Returns:
        Parsed config dict (e.g. llm_model, other app settings).
    """
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_csv(data_file_path: str = DATA_FILE_PATH) -> str:
    """
    Load a CSV file as raw text. For policy lookup use tools.data_lookup.lookup_policy_in_csv.

    Args:
        data_file_path: Path to the CSV file (default: DATA_FILE_PATH).

    Returns:
        The entire file content as a string.
    """
    with open(data_file_path, "r", encoding="utf-8") as f:
        return f.read()