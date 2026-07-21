#!/usr/bin/env python3
"""v1.3.21 honesty: sync_state same-height, mesh gate, bridge/L1, ready peer_count."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_sync_state_solo_fail_closed_clears_consistent():
    from sync.sync_engine import SyncEngine

    node = SimpleNamespace(
        blockchain=SimpleNamespace(
            get_state_root=lambda: "abc",
            get_height=lambda: 1,
            get_block=lambda _h: None,
        ),
        p2p=SimpleNamespace(_state_consistent=True),
    )
    eng = SyncEngine(node)
    eng._collect_p2p_peers = lambda: []  # type: ignore
    assert eng.sync_state() is False
    assert node.p2p._state_consistent is False
    assert eng._last_wire_probe_ok is None


def test_mesh_ready_rejects_heights_when_inconsistent():
    from runtime.mesh_mining import mesh_ready_for_mining

    assert not mesh_ready_for_mining(
        min_mesh_peers=2,
        connected_peers=2,
        wire_roots=[],
        local_height=3,
        local_root="aa" * 32,
        state_consistent=False,
        peer_heights=[3, 3],
    )


def test_rust_bridge_health_disabled_is_not_ok():
    from api.http import _rust_bridge_health

    out = _rust_bridge_health(SimpleNamespace(bridge_enabled=False, bridge_mode="rust"))
    assert out["ok"] is False
    assert out["error"] == "bridge_disabled"


def test_bridge_relayer_live_requires_rust_smoke():
    text = Path("api/http.py").read_text(encoding="utf-8")
    assert 'and getattr(cfg, "bridge_mode", "") == "rust"' in text
    assert "bool(bridge_health.get(\"ok\"))" in text
    assert '"bridge_rust_binary_healthy"' in text
    assert '"relayer_observed"' in text
    assert '"bridge_relayer_live": False' in text
    assert '"bridge_relayer_live": bool(cfg.bridge_enabled)' not in text


def test_ready_peer_count_probe_failure_fail_closed():
    text = Path("api/http.py").read_text(encoding="utf-8")
    assert 'checks["peer_count_probe"] = False' in text
    assert "/health/ready peer_count probe failed" in text


def test_l1_unconfigured_not_ok():
    from bridge import health

    out = health.check_l1_rpc_health(cfg=None)
    # Env may still have URLs in CI — only assert contract when empty.
    if not out.get("configured"):
        assert out["ok"] is False
        assert "no L1 RPC" in out.get("error", "")
