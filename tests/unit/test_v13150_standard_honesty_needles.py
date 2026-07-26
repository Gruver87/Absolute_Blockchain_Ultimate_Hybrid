#!/usr/bin/env python3
"""v1.3.150: Standard pytest honesty needles after ATXV/ABLK + new_tx rate."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.config import Config


def test_needles_v13150():
    notes = (ROOT / "RELEASE_NOTES_v1.3.150.md").read_text(encoding="utf-8")
    assert "1.3.150-industrial" in notes
    assert Config().node_version.startswith("1.3.")
    p2p_test = (ROOT / "tests" / "unit" / "test_p2p_industrial.py").read_text(
        encoding="utf-8"
    )
    assert "MSG_NEW_TX not in RATE_LIMIT_EXEMPT_TYPES" in p2p_test
    supply = (ROOT / "tests" / "unit" / "test_supply_broadcast_honesty.py").read_text(
        encoding="utf-8"
    )
    assert "_loads_tx_blob_or_none" in supply
    assert "_loads_block_blob_or_none" in supply
