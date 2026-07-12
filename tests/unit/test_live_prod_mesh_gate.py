#!/usr/bin/env python3
"""Live prod mesh gate (host ports :18180-:18182)."""

import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

_spec = importlib.util.spec_from_file_location(
    "verify_prod_stack", os.path.join(ROOT, "scripts", "verify_prod_stack.py")
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
check_live_prod_mesh = _mod.check_live_prod_mesh


def test_live_prod_mesh_gate_runs():
    errors = check_live_prod_mesh()
    assert isinstance(errors, list)
