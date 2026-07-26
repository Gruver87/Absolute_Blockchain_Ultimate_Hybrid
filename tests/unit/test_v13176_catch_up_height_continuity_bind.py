#!/usr/bin/env python3
"""v1.3.176: catch-up import height must equal expected sync cursor."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from network.p2p_node import P2PNode
from runtime.config import Config


def _node() -> P2PNode:
    cfg = Config()
    cfg.p2p_native_transport = False
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.bootstrap_peers = []
    cfg.p2p_catch_up_height_continuity_bind = True
    chain = MagicMock()
    chain.get_height.return_value = 10
    chain.get_state_root.return_value = "ee" * 32
    chain.get_block_by_hash = MagicMock(return_value=None)
    node = P2PNode(cfg, chain, MagicMock())
    node.head = MagicMock(return_value="aa" * 32)  # type: ignore[method-assign]
    return node


def test_needles_v13176():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "catch_up_height_continuity_mismatch" in p2p
    assert "_catch_up_height_continuity_refuse_reason" in p2p
    assert "native_catch_up_height_continuity_bind" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "p2p_catch_up_height_continuity_bind" in cfg
    assert "P2P_CATCH_UP_HEIGHT_CONTINUITY_BIND" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.176.md").read_text(encoding="utf-8")
    assert "1.3.176-industrial" in notes
    assert Config().node_version.startswith("1.3.176")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_catch_up_height_continuity_bind" in metrics
    assert "abs_p2p_catch_up_height_continuity_mismatch_total" in metrics


def test_refuse_skip_ahead():
    node = _node()
    assert (
        node._catch_up_height_continuity_refuse_reason(
            {"height": 15, "hash": "cc" * 32}, 11
        )
        == "catch_up_height_continuity_mismatch"
    )


def test_ok_matching_cursor():
    node = _node()
    assert (
        node._catch_up_height_continuity_refuse_reason(
            {"height": 11, "hash": "cc" * 32}, 11
        )
        == ""
    )


def test_bump_and_security_status():
    node = _node()
    reason = node._catch_up_height_continuity_refuse_reason(
        {"height": 99, "hash": "cc" * 32}, 11
    )
    assert reason == "catch_up_height_continuity_mismatch"
    node._bump_catch_up_refuse(reason)
    assert node._catch_up_height_continuity_mismatch_total >= 1
    st = node.get_p2p_security_status()
    assert st.get("native_catch_up_height_continuity_bind") is True
    assert int(st.get("catch_up_height_continuity_mismatch_total", 0) or 0) >= 1
