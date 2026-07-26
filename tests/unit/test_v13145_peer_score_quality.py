#!/usr/bin/env python3
"""v1.3.145: peer health score includes strikes + import fails."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from network.p2p_node import PeerConnection, P2PNode, _peer_health_score
from runtime.config import Config


class _W:
    def get_extra_info(self, _name, default=None):
        return ("127.0.0.1", 5001)

    def is_closing(self):
        return False

    def close(self):
        return None

    def write(self, _data):
        return None

    async def drain(self):
        return None


class _R:
    async def read(self, _n):
        return b""


def test_needles_v13145():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "native_peer_score_quality" in p2p
    assert "_score_peer" in p2p
    assert "_note_peer_import_fail" in p2p
    assert "quality_import_fails" in p2p
    assert "strikes + import_fails" in p2p or "import_fails" in p2p
    notes = (ROOT / "RELEASE_NOTES_v1.3.145.md").read_text(encoding="utf-8")
    assert "1.3.145-industrial" in notes
    assert Config().node_version.startswith("1.3.")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_peer_score_quality" in metrics


def test_score_penalizes_strikes_and_import_fails():
    cfg = Config()
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.bootstrap_peers = []
    cfg.p2p_rate_limit_strikes = 10
    node = P2PNode(cfg, MagicMock(), MagicMock())
    node._rl_table = None
    peer = PeerConnection(_R(), _W())
    peer.peer_id = "q1"
    peer.height = 10
    peer.last_seen = time.time()
    node.peers["q1"] = peer
    base = node._score_peer(peer, local_height=10, health_timeout=60)
    assert base == 100
    node._peer_strikes[node._peer_key(peer)] = 2
    mid = node._score_peer(peer, local_height=10, health_timeout=60)
    assert mid == 100 - 24
    node._note_peer_import_fail(peer)
    node._note_peer_import_fail(peer)
    low = node._score_peer(peer, local_height=10, health_timeout=60)
    assert low == 100 - 24 - 20
    assert peer.quality_import_fails == 2
    st = node.get_p2p_security_status()
    assert st.get("native_peer_score_quality") is True


def test_helper_caps_strike_and_import_penalties():
    # Caps: strikes max -48, import_fails max -40
    assert (
        _peer_health_score(
            height_gap=0,
            last_seen_age=0,
            health_timeout=60,
            strikes=99,
            import_fails=99,
        )
        == 100 - 48 - 40
    )
