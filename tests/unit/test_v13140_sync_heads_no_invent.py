#!/usr/bin/env python3
"""v1.3.140: SyncEngine never invents peer.head from local blocks."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.config import Config
from sync.sync_engine import SyncEngine


class _Peer:
    def __init__(self, head, height=0, peer_id="p1"):
        self.head = head
        self.height = height
        self.peer_id = peer_id


class _Chain:
    def get_height(self):
        return 10

    def get_block(self, height: int):
        # Would previously invent peer.head from this local tip — must not.
        return {"hash": "ff" * 32, "height": height}


class _Node:
    def __init__(self, peers):
        self.p2p = type("P2P", (), {"peers": {p.peer_id: p for p in peers}})()
        self.blockchain = _Chain()
        self.consensus = None


def test_needles_v13140():
    sync = (ROOT / "sync" / "sync_engine.py").read_text(encoding="utf-8")
    assert "never invent peer.head" in sync
    assert "heads_skipped_no_head" in sync
    assert "native_sync_heads_no_invent" in sync
    # Old invent path must be gone
    assert "get_block(peer.height)" not in sync
    notes = (ROOT / "RELEASE_NOTES_v1.3.140.md").read_text(encoding="utf-8")
    assert "1.3.140-industrial" in notes
    assert Config().node_version.startswith("1.3.")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_sync_heads_no_invent" in metrics
    assert "abs_p2p_heads_skipped_no_head" in metrics
    check = (ROOT / "scripts" / "check_all.ps1").read_text(encoding="utf-8")
    assert 'EvidenceGitTag = "v1.3.139"' in check or "v1.3.140" in check or "v1.3.141" in check or "v1.3.142" in check or "v1.3.143" in check or "v1.3.144" in check or "v1.3.145" in check or "v1.3.146" in check or "v1.3.147" in check or "v1.3.148" in check or "v1.3.149" in check or "v1.3.150" in check or "v1.3.151" in check or "v1.3.152" in check or "v1.3.153" in check or "v1.3.154" in check or "v1.3.155" in check or "v1.3.156" in check or "v1.3.157" in check or "v1.3.158" in check


def test_request_heads_skips_empty_head_no_local_invent():
    peers = [
        _Peer("", height=10, peer_id="no-head"),
        _Peer("ab" * 32, height=10, peer_id="ok"),
    ]
    engine = SyncEngine(node=_Node(peers))
    heads = engine.request_heads()
    assert len(heads) == 1
    assert heads[0]["peer_id"] == "ok"
    assert engine._heads_skipped_no_head == 1
    st = engine.get_status()
    assert st.get("native_sync_heads_no_invent") is True
    assert st.get("heads_skipped_no_head") == 1
