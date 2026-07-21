"""external_audit bridge automation uses bridge_off_audit_gate."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_automated_bridge_l1_keys_passes():
    from runtime.external_audit import _automated_bridge_l1_keys

    ok, note = _automated_bridge_l1_keys(ROOT)
    assert ok is True
    assert "bridge_off_audit_gate" in note
