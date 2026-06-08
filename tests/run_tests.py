# tests/run_tests.py
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

if __name__ == "__main__":
    result = pytest.main(["tests/unit", "-v"])
    sys.exit(result)
