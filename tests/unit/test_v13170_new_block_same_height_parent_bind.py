#!/usr/bin/env python3
"""v1.3.170: same-height NEW_BLOCK parent must match tip-height parent."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from network.p2p_node import P2PNode
from runtime.config import Config

TIP = "aa" * 32
SIBLING = "bb" * 32
PARENT = "11" * 32
WRONG_PARENT = "22" * 32


def _node() -> P2PNode:
    cfg = Config()
    cfg.p2p_native_transport = False
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.bootstrap_peers = []
    cfg.p2p_new_block_same_height_parent_bind = True
    chain = MagicMock()
    chain.get_height.return_value = 10
    chain.get_state_root.return_value = "ee" * 32
    chain.get_block_by_hash = MagicMock(return_value=None)
    chain.get_block = MagicMock(return_value={"hash": PARENT, "height": 9})
    node = P2PNode(cfg, chain, MagicMock())
    node.head = MagicMock(return_value=TIP)  # type: ignore[method-assign]
    return node


def test_needles_v13170():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "new_block_same_height_parent_mismatch" in p2p
    assert "_new_block_same_height_parent_refuse_reason" in p2p
    assert "native_new_block_same_height_parent_bind" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "p2p_new_block_same_height_parent_bind" in cfg
    assert "P2P_NEW_BLOCK_SAME_HEIGHT_PARENT_BIND" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.170.md").read_text(encoding="utf-8")
    assert "1.3.170-industrial" in notes
    assert Config().node_version.startswith("1.3.170")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_new_block_same_height_parent_bind" in metrics
    assert "abs_p2p_new_block_same_height_parent_mismatch_total" in metrics


def test_refuse_wrong_parent():
    node = _node()
    block = SimpleNamespace(height=10, hash=SIBLING, parent_hash=WRONG_PARENT)
    assert (
        node._new_block_same_height_parent_refuse_reason(block, 10)
        == "new_block_same_height_parent_mismatch"
    )


def test_ok_matching_parent():
    node = _node()
    block = SimpleNamespace(height=10, hash=SIBLING, parent_hash=PARENT)
    assert node._new_block_same_height_parent_refuse_reason(block, 10) == ""


def test_idempotent_local_tip_skips():
    node = _node()
    block = SimpleNamespace(height=10, hash=TIP, parent_hash=WRONG_PARENT)
    assert node._new_block_same_height_parent_refuse_reason(block, 10) == ""


def test_non_same_height_skips():
    node = _node()
    block = SimpleNamespace(height=11, hash=SIBLING, parent_hash=WRONG_PARENT)
    assert node._new_block_same_height_parent_refuse_reason(block, 10) == ""


def test_security_status_gauge():
    node = _node()
    st = node.get_p2p_security_status()
    assert st.get("native_new_block_same_height_parent_bind") is True
