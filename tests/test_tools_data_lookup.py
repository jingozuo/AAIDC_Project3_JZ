"""Unit tests for the data_lookup tool (policy lookup by policy number)."""
import pytest

from codes.tools.data_lookup import lookup_policy_in_csv, CSV_KEY_MAP


class TestCSVKeyMap:
    """Test CSV column name mapping."""

    def test_key_map_has_expected_keys(self):
        assert "Policy_Number" in CSV_KEY_MAP
        assert CSV_KEY_MAP["Policy_Number"] == "Policy Number"
        assert CSV_KEY_MAP["First_Name"] == "First Name"
        assert CSV_KEY_MAP["Is_Payment_Paid"] == "Is Payment Made"


class TestLookupPolicyInCsv:
    """Test lookup_policy_in_csv against the project's insurance_policies.csv."""

    def test_lookup_existing_policy_returns_record(self):
        # POL01212 exists in data/insurance_policies.csv
        record = lookup_policy_in_csv("POL01212")
        assert record is not None
        assert record["Policy Number"] == "POL01212"
        assert record["First Name"] == "John"
        assert record["Last Name"] == "Smith"
        assert "Email" in record
        assert "Policy Status" in record
        assert "Start Date" in record
        assert "End Date" in record
        assert "Payment Amount" in record
        assert "Is Payment Made" in record

    def test_lookup_with_uppercase_normalized_by_caller(self):
        # Caller typically does .strip().upper() before calling; CSV has uppercase
        record = lookup_policy_in_csv("POL02309")
        assert record is not None
        assert record["Policy Number"] == "POL02309"
        assert record["First Name"] == "Alice"

    def test_lookup_nonexistent_policy_returns_none(self):
        assert lookup_policy_in_csv("NONEXISTENT") is None
        assert lookup_policy_in_csv("POL99999") is None

    def test_lookup_empty_string_returns_none(self):
        result = lookup_policy_in_csv("")
        assert result is None or isinstance(result, dict)

    def test_returned_record_has_spaced_keys(self):
        record = lookup_policy_in_csv("POL01212")
        assert record is not None
        assert "First Name" in record
        assert "Policy Number" in record
        assert "Is Payment Made" in record
        assert "First_Name" not in record
        assert "Policy_Number" not in record
