#!/usr/bin/env python3
"""v1.3.181: GET_BLOCK refused when height > local tip."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from network.p2p_node import P2PNode
from runtime.config import Config


def _node(*, local_h: int = 10) -> P2PNode:
    cfg = Config()
    cfg.p2p_native_transport = False
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.bootstrap_peers = []
    cfg.p2p_get_block_future_refuse = True
    chain = MagicMock()
    chain.get_height.return_value = local_h
    chain.get_state_root.return_value = "ee" * 32
    chain.get_block = MagicMock(return_value={"hash": "aa" * 32, "height": local_h})
    return P2PNode(cfg, chain, MagicMock())


def test_needles_v13181():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "get_block_future_height" in p2p
    assert "_get_block_future_refuse_reason" in p2p
    assert "native_get_block_future_refuse" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "p2p_get_block_future_refuse" in cfg
    assert "P2P_GET_BLOCK_FUTURE_REFUSE" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.181.md").read_text(encoding="utf-8")
    assert "1.3.181-industrial" in notes
    assert Config().node_version.startswith("1.3.")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_get_block_future_refuse" in metrics
    assert "abs_p2p_get_block_future_refuse_total" in metrics


def test_refuse_future_height():
    node = _node(local_h=10)
    assert node._get_block_future_refuse_reason(11) == "get_block_future_height"
    assert node._get_block_future_refuse_reason(999) == "get_block_future_height"


def test_ok_at_or_below_tip():
    node = _node(local_h=10)
    assert node._get_block_future_refuse_reason(10) == ""
    assert node._get_block_future_refuse_reason(0) == ""


def test_bump_and_security_status():
    node = _node(local_h=10)
    reason = node._get_block_future_refuse_reason(50)
    assert reason == "get_block_future_height"
    node._get_block_future_refuse_total = int(
        getattr(node, "_get_block_future_refuse_total", 0) or 0
    ) + 1
    st = node.get_p2p_security_status()
    assert st.get("native_get_block_future_refuse") is True
    assert int(st.get("get_block_future_refuse_total", 0) or 0) >= 1
