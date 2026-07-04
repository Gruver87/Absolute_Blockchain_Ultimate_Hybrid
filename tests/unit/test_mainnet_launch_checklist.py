#!/usr/bin/env python3
"""Mainnet launch checklist smoke test."""

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location(
    "mainnet_launch_checklist",
    ROOT / "scripts" / "mainnet_launch_checklist.py",
)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def test_launch_checklist_passes_non_strict():
    errors, warnings = mod.run_launch_checklist(strict_mainnet=False)
    assert not errors, errors
