"""bridge_off_audit_gate static checks."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "bridge_off_audit_gate.py"


def _load():
    spec = importlib.util.spec_from_file_location("bridge_off_audit_gate", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_bridge_off_audit_gate_passes():
    mod = _load()
    assert mod.main() == 0
