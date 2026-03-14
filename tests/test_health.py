"""Tests for codes.health: run_health_checks and individual checks."""
import os
import tempfile

import pytest

from codes.health import run_health_checks, _check_config, _check_data, _check_directories
from codes.paths import CONFIG_FILE_PATH, PROMPT_CONFIG_FILE_PATH, DATA_FILE_PATH, OUTPUTS_DIR, LOGS_DIR


class TestCheckConfig:
    def test_check_config_succeeds_when_files_valid(self):
        if os.path.isfile(CONFIG_FILE_PATH) and os.path.isfile(PROMPT_CONFIG_FILE_PATH):
            r = _check_config(verbose=False)
            assert r["name"] == "config"
            assert r["ok"] is True
            assert "valid" in r["message"].lower()

    def test_check_config_fails_when_main_missing(self, monkeypatch):
        with tempfile.TemporaryDirectory() as d:
            fake_path = os.path.join(d, "config.yaml")
            monkeypatch.setattr("codes.health.CONFIG_FILE_PATH", fake_path)
            r = _check_config(verbose=False)
            assert r["ok"] is False
            assert "not found" in r["message"].lower() or "config" in r["message"].lower()


class TestCheckData:
    def test_check_data_succeeds_when_file_exists(self):
        if os.path.isfile(DATA_FILE_PATH):
            r = _check_data(verbose=False)
            assert r["name"] == "data"
            assert r["ok"] is True

    def test_check_data_fails_when_file_missing(self, monkeypatch):
        monkeypatch.setattr("codes.health.DATA_FILE_PATH", "/nonexistent/insurance_policies.csv")
        r = _check_data(verbose=False)
        assert r["ok"] is False
        assert "not found" in r["message"].lower() or "Data" in r["message"]


class TestCheckDirectories:
    def test_check_directories_succeeds_when_writable(self):
        r = _check_directories(verbose=False)
        assert r["name"] == "directories"
        assert r["ok"] is True
        assert os.path.isdir(OUTPUTS_DIR)
        assert os.path.isdir(LOGS_DIR)


class TestRunHealthChecks:
    def test_run_health_checks_returns_dict_with_ok_and_results(self):
        out = run_health_checks(skip_llm=True, verbose=False)
        assert "ok" in out
        assert "results" in out
        assert isinstance(out["results"], list)
        assert len(out["results"]) >= 3  # config, data, directories

    def test_run_health_checks_skip_llm_includes_llm_as_skipped(self):
        out = run_health_checks(skip_llm=True, verbose=False)
        llm_results = [r for r in out["results"] if r["name"] == "llm"]
        assert len(llm_results) == 1
        assert llm_results[0].get("skipped") is True

    def test_run_health_checks_all_pass_when_project_valid(self):
        if not os.path.isfile(CONFIG_FILE_PATH) or not os.path.isfile(DATA_FILE_PATH):
            pytest.skip("Project config/data not present")
        out = run_health_checks(skip_llm=True, verbose=True)
        assert out["ok"] is True
        for r in out["results"]:
            assert r["ok"] is True or r.get("skipped") is True
