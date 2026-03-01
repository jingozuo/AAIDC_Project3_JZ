#!/usr/bin/env python3
"""
Run tests (unit, integration, e2e). Adds project root to sys.path so 'codes' is importable.

Run this script with Python, NOT with pytest:
  python3 tests/run_tests.py [pytest options]   # from project root
  python3 run_tests.py [pytest options]         # from tests/ dir

Do NOT run: pytest run_tests.py  (that runs pytest on this file, which has no tests.)

Examples:
  python3 tests/run_tests.py -v
  python3 tests/run_tests.py -v -s              # include e2e (needs -s for input mocking)
  python3 tests/run_tests.py -m "not e2e" -v   # unit + integration only
"""
import os
import sys

# This file lives in tests/; project root is parent of tests/
_tests_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_tests_dir)

if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pytest

if __name__ == "__main__":
    default_args = ["-v", "--tb=short", _tests_dir]
    args = sys.argv[1:] if len(sys.argv) > 1 else default_args
    sys.exit(pytest.main(args))
