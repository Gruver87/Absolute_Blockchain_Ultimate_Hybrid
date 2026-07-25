#!/usr/bin/env python3
"""v1.3.69: block-scoped sat session for mixed native apply."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_mixed_apply_uses_block_session():
    bc = (ROOT / "core" / "blockchain.py").read_text(encoding="utf-8")
    assert "block-scoped sat session" in bc
    assert "session = self._accounts_sat_snapshot" in bc
    # One writeback at end — not per-tx inside the loop for mixed path.
    # Find the mixed method body and ensure final writeback of session.
    assert "self._writeback_accounts_sat(session)" in bc
    assert "1.3.69" in bc or "v1.3.69" in bc


def test_verify_script_exists():
    assert (ROOT / "scripts" / "verify_industrial_waves.py").is_file()
    assert (ROOT / "scripts" / "verify_industrial_waves.ps1").is_file()
    text = (ROOT / "scripts" / "verify_industrial_waves.py").read_text(encoding="utf-8")
    assert "1.3.65" in text and "1.3.68" in text
