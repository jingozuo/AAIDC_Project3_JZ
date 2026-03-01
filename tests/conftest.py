"""
Pytest configuration for unit tests (tests at project root in tests/).

Run from project root: python3 -m pytest tests/ -v
Or: python3 run_tests.py

Adds project root to sys.path so that 'from codes.tools.xxx' and 'from codes.nodes' work.
Mocks codes.llm so importing codes.nodes does not pull in langchain/torch.
"""
import os
import sys
from unittest.mock import MagicMock

# tests/conftest.py -> project root is parent of tests/
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Mock codes.llm before any test imports codes.nodes (nodes imports llm -> langchain -> torch)
if "codes.llm" not in sys.modules:
    sys.modules["codes.llm"] = MagicMock()


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: end-to-end system tests (run with -s for input mocking)")
    # Suppress Typer deprecation warning from deepeval/other deps (not our code)
    config.addinivalue_line(
        "filterwarnings",
        "ignore:The 'is_flag' and 'flag_value' parameters are not supported by Typer:DeprecationWarning",
    )
