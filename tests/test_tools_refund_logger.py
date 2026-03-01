"""Unit tests for the refund_logger tool (persist refund records to CSV)."""
import csv
import os
import pytest

from codes.tools import refund_logger as refund_logger_module


class TestLogRefundRecord:
    """Test log_refund_record with a temporary output directory."""

    def test_log_refund_record_creates_file_and_returns_true(self, tmp_path, monkeypatch):
        monkeypatch.setattr(refund_logger_module, "OUTPUTS_DIR", str(tmp_path))
        monkeypatch.setattr(
            refund_logger_module,
            "REFUND_LOG_FILE_PATH",
            os.path.join(str(tmp_path), "refund_log.csv"),
        )
        policy = {
            "policy_number": "POL01212",
            "first_name": "John",
            "last_name": "Smith",
            "email": "john@example.com",
        }
        result = refund_logger_module.log_refund_record(
            policy, 150.50, "Refund amount calculated successfully."
        )
        assert result is True
        log_path = tmp_path / "refund_log.csv"
        assert log_path.exists()
        with open(log_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["Policy_number"] == "POL01212"
        assert rows[0]["First_name"] == "John"
        assert rows[0]["Refund_amount"] == "150.5"
        assert "Refund_record_id" in rows[0]
        assert "Request_date" in rows[0]

    def test_log_refund_record_appends_second_record(self, tmp_path, monkeypatch):
        monkeypatch.setattr(refund_logger_module, "OUTPUTS_DIR", str(tmp_path))
        monkeypatch.setattr(
            refund_logger_module,
            "REFUND_LOG_FILE_PATH",
            os.path.join(str(tmp_path), "refund_log.csv"),
        )
        policy = {"policy_number": "P1", "first_name": "A", "last_name": "B", "email": "a@b.com"}
        refund_logger_module.log_refund_record(policy, 100.0, "Reason 1")
        refund_logger_module.log_refund_record(policy, 200.0, "Reason 2")
        log_path = tmp_path / "refund_log.csv"
        with open(log_path, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
        assert float(rows[0]["Refund_amount"]) == 100.0
        assert float(rows[1]["Refund_amount"]) == 200.0


class TestGetNextRefundRecordId:
    """Test get_next_refund_record_id."""

    def test_returns_1_when_file_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            refund_logger_module,
            "REFUND_LOG_FILE_PATH",
            os.path.join(str(tmp_path), "nonexistent_refund_log.csv"),
        )
        assert refund_logger_module.get_next_refund_record_id() == 1

    def test_returns_count_plus_one_when_file_exists(self, tmp_path, monkeypatch):
        log_path = tmp_path / "refund_log.csv"
        log_path.write_text(
            "Refund_record_id,Request_date,Policy_number,First_name,Last_name,Email,Refund_amount,Refund_reason\n"
            "1,2025-01-01 12:00:00,P1,A,B,a@b.com,100,Reason\n"
        )
        monkeypatch.setattr(refund_logger_module, "REFUND_LOG_FILE_PATH", str(log_path))
        assert refund_logger_module.get_next_refund_record_id() == 2
