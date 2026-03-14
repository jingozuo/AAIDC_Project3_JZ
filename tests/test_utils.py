"""Tests for codes.utils: load_config, load_csv, ConfigError."""
import os
import tempfile
from pathlib import Path

import pytest
import yaml

from codes.utils import load_config, load_csv, ConfigError
from codes.paths import CONFIG_FILE_PATH, DATA_FILE_PATH


class TestConfigError:
    def test_config_error_is_exception(self):
        assert issubclass(ConfigError, Exception)
        e = ConfigError("test")
        assert str(e) == "test"


class TestLoadConfig:
    def test_load_config_missing_file_raises(self):
        with pytest.raises(ConfigError, match="Config file not found"):
            load_config("/nonexistent/path.yaml")

    def test_load_config_empty_path_raises(self):
        with pytest.raises(ConfigError, match="Config file not found"):
            load_config("")

    def test_load_config_invalid_yaml_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            f.write(b"not: valid: yaml: [")
            f.flush()
            try:
                with pytest.raises(ConfigError, match="Invalid YAML"):
                    load_config(f.name)
            finally:
                os.unlink(f.name)

    def test_load_config_empty_file_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            f.write(b"")
            f.flush()
            try:
                with pytest.raises(ConfigError, match="empty"):
                    load_config(f.name)
            finally:
                os.unlink(f.name)

    def test_load_config_non_dict_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            f.write(b"just a string")
            f.flush()
            try:
                with pytest.raises(ConfigError, match="YAML object"):
                    load_config(f.name)
            finally:
                os.unlink(f.name)

    def test_load_config_success_returns_dict(self):
        # Use project config if present
        if os.path.isfile(CONFIG_FILE_PATH):
            data = load_config(CONFIG_FILE_PATH)
            assert isinstance(data, dict)
            assert "llm_model" in data


class TestLoadCsv:
    def test_load_csv_missing_file_raises(self):
        with pytest.raises(ConfigError, match="Data file not found"):
            load_csv("/nonexistent/data.csv")

    def test_load_csv_success_returns_string(self):
        if os.path.isfile(DATA_FILE_PATH):
            content = load_csv(DATA_FILE_PATH)
            assert isinstance(content, str)
            assert len(content) >= 0
