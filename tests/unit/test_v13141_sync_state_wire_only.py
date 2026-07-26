#!/usr/bin/env python3
"""v1.3.141: sync_state same-height match is wire-only (no local invent)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.config import Config
from sync.sync_engine import SyncEngine

LOCAL_ROOT = "aa" * 32


def test_needles_v13141():
    sync = (ROOT / "sync" / "sync_engine.py").read_text(encoding="utf-8")
    assert "same-height consistency only from wire roots" in sync
    assert "native_sync_state_wire_only" in sync
    assert "get_block(peer_height)" not in sync
    assert "get_block(peer.height)" not in sync
    notes = (ROOT / "RELEASE_NOTES_v1.3.141.md").read_text(encoding="utf-8")
    assert "1.3.141-industrial" in notes
    assert Config().node_version.startswith("1.3.")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_sync_state_wire_only" in metrics
    check = (ROOT / "scripts" / "check_all.ps1").read_text(encoding="utf-8")
    assert "v1.3.140" in check or "v1.3.141" in check or "v1.3.142" in check or "v1.3.143" in check or "v1.3.144" in check or "v1.3.145" in check or "v1.3.146" in check or "v1.3.147" in check or "v1.3.148" in check or "v1.3.149" in check or "v1.3.150" in check or "v1.3.151" in check or "v1.3.152" in check or "v1.3.153" in check or "v1.3.154" in check or "v1.3.155" in check or "v1.3.156" in check or "v1.3.157" in check or "v1.3.158" in check or "v1.3.159" in check or "v1.3.160" in check or "v1.3.161" in check or "v1.3.162" in check or "v1.3.163" in check or "v1.3.164" in check or "v1.3.165" in check or "v1.3.166" in check or "v1.3.167" in check or "v1.3.168" in check or "v1.3.169" in check or "v1.3.170" in check or "v1.3.171" in check or "v1.3.172" in check or "v1.3.173" in check or "v1.3.174" in check or "v1.3.175" in check or "v1.3.176" in check or "v1.3.177" in check or "v1.3.178" in check


def test_sync_state_no_local_invent_when_wire_lacks_same_height():
    """Peer height == local + local tip matches must NOT paint green without wire."""
    peer = SimpleNamespace(peer_id="peer1", height=5)
    local_blk = {"hash": "ff" * 32, "height": 5, "state_root": LOCAL_ROOT}
    node = SimpleNamespace(
        blockchain=SimpleNamespace(
            get_state_root=lambda: LOCAL_ROOT,
            get_height=lambda: 5,
            get_block=lambda _h: local_blk,
        ),
        # Wire probe "ok" but only behind / empty same-height root — old path
        # would invent match from local get_block(peer_height).
        request_peer_state_roots_sync=MagicMock(
            return_value=[
                {"peer_id": "peer1", "height": 3, "state_root": LOCAL_ROOT},
                {"peer_id": "peer1", "height": 5, "state_root": ""},
            ]
        ),
        p2p=SimpleNamespace(_state_consistent=True, peers={"peer1": peer}),
    )
    eng = SyncEngine(node)
    ok = eng.sync_state()
    assert ok is False
    assert node.p2p._state_consistent is False
    assert eng.get_status().get("native_sync_state_wire_only") is True


def test_sync_state_wire_same_height_match_still_green():
    peer = SimpleNamespace(peer_id="peer1", height=5)
    node = SimpleNamespace(
        blockchain=SimpleNamespace(
            get_state_root=lambda: LOCAL_ROOT,
            get_height=lambda: 5,
            get_block=lambda _h: None,
        ),
        request_peer_state_roots_sync=MagicMock(
            return_value=[
                {"peer_id": "peer1", "height": 5, "state_root": LOCAL_ROOT},
            ]
        ),
        p2p=SimpleNamespace(_state_consistent=False, peers={"peer1": peer}),
    )
    eng = SyncEngine(node)
    assert eng.sync_state() is True
    assert node.p2p._state_consistent is True
