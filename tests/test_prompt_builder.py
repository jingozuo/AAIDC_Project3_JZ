"""Unit tests for the prompt_builder module."""
import pytest

from codes.prompt_builder import (
    lowercase_first_char,
    format_prompt_section,
    build_prompt_from_config,
)


class TestLowercaseFirstChar:
    """Test lowercase_first_char."""

    def test_lowercases_first_char(self):
        assert lowercase_first_char("Hello") == "hello"

    def test_empty_string_returns_empty(self):
        assert lowercase_first_char("") == ""

    def test_single_char(self):
        assert lowercase_first_char("A") == "a"


class TestFormatPromptSection:
    """Test format_prompt_section."""

    def test_string_value_joins_with_lead_in(self):
        out = format_prompt_section("Your task:", "Do the thing.")
        assert "Your task:" in out
        assert "Do the thing." in out

    def test_list_value_formats_as_bullets(self):
        out = format_prompt_section("Rules:", ["Rule A", "Rule B"])
        assert "Rules:" in out
        assert "- Rule A" in out
        assert "- Rule B" in out


class TestBuildPromptFromConfig:
    """Test build_prompt_from_config."""

    def test_requires_instruction_raises(self):
        with pytest.raises(ValueError, match="instruction"):
            build_prompt_from_config({})

    def test_minimal_config_with_instruction(self):
        out = build_prompt_from_config({"instruction": "Answer the question."})
        assert "Answer the question." in out
        assert "Now perform the task" in out

    def test_role_lowercased(self):
        out = build_prompt_from_config({
            "role": "You are an assistant.",
            "instruction": "Help.",
        })
        assert "you are" in out.lower() or "assistant" in out

    def test_input_data_string_appended_as_content(self):
        out = build_prompt_from_config(
            {"instruction": "Summarize."},
            input_data="Some text to summarize.",
        )
        assert "BEGIN CONTENT" in out
        assert "END CONTENT" in out
        assert "Some text to summarize." in out

    def test_input_data_dict_serialized_as_json(self):
        out = build_prompt_from_config(
            {"instruction": "Process."},
            input_data={"key": "value"},
        )
        assert "key" in out
        assert "value" in out
        assert "BEGIN CONTENT" in out
