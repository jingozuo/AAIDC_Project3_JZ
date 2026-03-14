"""
Utility functions for config and data loading.

Role: load_config reads a YAML file (default paths.CONFIG_FILE_PATH) and returns a dict.
load_csv reads a CSV file as raw text (default paths.DATA_FILE_PATH). Used by main and
other callers that need config or raw CSV content. For structured policy lookup, use
tools.data_lookup.lookup_policy_in_csv instead of load_csv.
"""
import os
import yaml
from typing import Any, Dict

from codes.paths import CONFIG_FILE_PATH, DATA_FILE_PATH, OUTPUTS_DIR
from codes.llm import get_llm


class ConfigError(Exception):
    """Raised when config/data file is missing, invalid, or unreadable."""


def load_config(config_path: str = CONFIG_FILE_PATH) -> Dict[str, Any]:
    """
    Load a YAML config file and return the parsed dict.

    Args:
        config_path: Path to the YAML file (default: CONFIG_FILE_PATH).

    Returns:
        Parsed config dict (e.g. llm_model, other app settings).

    Raises:
        ConfigError: If file is missing, unreadable, invalid YAML, or empty.
    """
    if not config_path or not os.path.isfile(config_path):
        raise ConfigError(f"Config file not found: {config_path}")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except OSError as e:
        raise ConfigError(f"Cannot read config file {config_path}: {e}") from e
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {config_path}: {e}") from e
    if data is None:
        raise ConfigError(f"Config file is empty: {config_path}")
    if not isinstance(data, dict):
        raise ConfigError(f"Config must be a YAML object (dict), got {type(data).__name__}")
    return data


def load_csv(data_file_path: str = DATA_FILE_PATH) -> str:
    """
    Load a CSV file as raw text. For policy lookup use tools.data_lookup.lookup_policy_in_csv.

    Args:
        data_file_path: Path to the CSV file (default: DATA_FILE_PATH).

    Returns:
        The entire file content as a string.

    Raises:
        ConfigError: If file is missing or unreadable (reused for file I/O errors).
    """
    if not os.path.isfile(data_file_path):
        raise ConfigError(f"Data file not found: {data_file_path}")
    try:
        with open(data_file_path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        raise ConfigError(f"Cannot read data file {data_file_path}: {e}") from e