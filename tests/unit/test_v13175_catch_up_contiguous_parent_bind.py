#!/usr/bin/env python3
"""v1.3.175: catch-up import at tip+1 must cite local tip as parent."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from network.p2p_node import P2PNode
from runtime.config import Config

TIP = "aa" * 32
WRONG_PARENT = "bb" * 32


def _node(*, tip_h: int = 10) -> P2PNode:
    cfg = Config()
    cfg.p2p_native_transport = False
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.bootstrap_peers = []
    cfg.p2p_catch_up_contiguous_parent_bind = True
    chain = MagicMock()
    chain.get_height.return_value = tip_h
    chain.get_state_root.return_value = "ee" * 32
    chain.get_block_by_hash = MagicMock(return_value=None)
    node = P2PNode(cfg, chain, MagicMock())
    node.head = MagicMock(return_value=TIP)  # type: ignore[method-assign]
    return node


def test_needles_v13175():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "catch_up_contiguous_parent_mismatch" in p2p
    assert "_catch_up_contiguous_parent_refuse_reason" in p2p
    assert "native_catch_up_contiguous_parent_bind" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "p2p_catch_up_contiguous_parent_bind" in cfg
    assert "P2P_CATCH_UP_CONTIGUOUS_PARENT_BIND" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.175.md").read_text(encoding="utf-8")
    assert "1.3.175-industrial" in notes
    assert Config().node_version.startswith("1.3.175")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_catch_up_contiguous_parent_bind" in metrics
    assert "abs_p2p_catch_up_contiguous_parent_mismatch_total" in metrics


def test_refuse_wrong_parent():
    node = _node(tip_h=10)
    assert (
        node._catch_up_contiguous_parent_refuse_reason(
            {"height": 11, "parent_hash": WRONG_PARENT, "hash": "cc" * 32}
        )
        == "catch_up_contiguous_parent_mismatch"
    )


def test_ok_matching_parent():
    node = _node(tip_h=10)
    assert (
        node._catch_up_contiguous_parent_refuse_reason(
            {"height": 11, "parent_hash": TIP, "hash": "cc" * 32}
        )
        == ""
    )


def test_non_contiguous_skips():
    node = _node(tip_h=10)
    assert (
        node._catch_up_contiguous_parent_refuse_reason(
            {"height": 12, "parent_hash": WRONG_PARENT, "hash": "cc" * 32}
        )
        == ""
    )


def test_empty_parent_skips():
    node = _node(tip_h=10)
    assert (
        node._catch_up_contiguous_parent_refuse_reason(
            {"height": 11, "parent_hash": "", "hash": "cc" * 32}
        )
        == ""
    )


def test_bump_and_security_status():
    node = _node(tip_h=10)
    reason = node._catch_up_contiguous_parent_refuse_reason(
        {"height": 11, "parent_hash": WRONG_PARENT, "hash": "cc" * 32}
    )
    assert reason == "catch_up_contiguous_parent_mismatch"
    node._bump_catch_up_refuse(reason)
    assert node._catch_up_contiguous_parent_mismatch_total >= 1
    st = node.get_p2p_security_status()
    assert st.get("native_catch_up_contiguous_parent_bind") is True
    assert int(st.get("catch_up_contiguous_parent_mismatch_total", 0) or 0) >= 1
