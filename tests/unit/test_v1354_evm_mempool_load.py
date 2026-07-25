#!/usr/bin/env python3
"""v1.3.54: EVM/mempool high-load harness (ChainApplyQueue under concurrent enqueue)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "evm_mempool_load_harness",
    ROOT / "scripts" / "evm_mempool_load_harness.py",
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
run_harness = _mod.run_harness


def test_harness_short_pass():
    report = run_harness(rounds=3, workers=2, batch=4, mix_evm=True)
    assert report["ok"] is True, report
    assert report["height_delta"] >= 1
    assert report["forged_ok"] >= 1
    assert report["forged_fail"] == 0
    assert report["recv_balance"] > 0
    assert report["apply_completed_total"] >= 1


def test_wiring():
    assert Path("scripts/evm_mempool_load_harness.py").is_file()
    text = Path("scripts/evm_mempool_load_harness.py").read_text(encoding="utf-8")
    assert "ChainApplyQueue" in text
    assert "submit_forge_and_apply" in text
    assert "urlopen" not in text
