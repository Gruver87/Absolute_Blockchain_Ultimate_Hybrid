#!/usr/bin/env python3
"""v1.3.174: after NEW_BLOCK import, tip hash must match announce hash."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from network.p2p_node import P2PNode
from runtime.config import Config

ANNOUNCE = "ab" * 32
WRONG_TIP = "aa" * 32


def _node(*, tip_h: int = 11) -> P2PNode:
    cfg = Config()
    cfg.p2p_native_transport = False
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.bootstrap_peers = []
    cfg.p2p_new_block_tip_head_bind = True
    chain = MagicMock()
    chain.get_height.return_value = tip_h
    chain.get_state_root.return_value = "ee" * 32
    chain.get_block_by_hash = MagicMock(return_value=None)
    node = P2PNode(cfg, chain, MagicMock())
    node.head = MagicMock(return_value=WRONG_TIP)  # type: ignore[method-assign]
    return node


def test_needles_v13174():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "new_block_tip_head_mismatch" in p2p
    assert "_new_block_tip_head_refuse_reason" in p2p
    assert "native_new_block_tip_head_bind" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "p2p_new_block_tip_head_bind" in cfg
    assert "P2P_NEW_BLOCK_TIP_HEAD_BIND" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.174.md").read_text(encoding="utf-8")
    assert "1.3.174-industrial" in notes
    assert Config().node_version.startswith("1.3.174")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_new_block_tip_head_bind" in metrics
    assert "abs_p2p_new_block_tip_head_mismatch_total" in metrics


def test_refuse_tip_mismatch():
    node = _node(tip_h=11)
    assert (
        node._new_block_tip_head_refuse_reason(ANNOUNCE, 11)
        == "new_block_tip_head_mismatch"
    )


def test_ok_matching_tip():
    node = _node(tip_h=11)
    node.head = MagicMock(return_value=ANNOUNCE)  # type: ignore[method-assign]
    assert node._new_block_tip_head_refuse_reason(ANNOUNCE, 11) == ""


def test_height_incomplete_skips():
    node = _node(tip_h=10)
    assert node._new_block_tip_head_refuse_reason(ANNOUNCE, 11) == ""


def test_empty_tip_skips():
    node = _node(tip_h=11)
    node.head = MagicMock(return_value="")  # type: ignore[method-assign]
    assert node._new_block_tip_head_refuse_reason(ANNOUNCE, 11) == ""


def test_security_status_gauge():
    node = _node()
    st = node.get_p2p_security_status()
    assert st.get("native_new_block_tip_head_bind") is True
