#!/usr/bin/env python3
"""v1.3.166: handshake head-only (height<=0) refused when local tip > 0."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from network.p2p_node import P2PNode
from runtime.config import Config

DIGEST = "ab" * 32


def _node(*, local_h: int = 10) -> P2PNode:
    cfg = Config()
    cfg.p2p_native_transport = False
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.bootstrap_peers = []
    cfg.p2p_handshake_head_requires_height = True
    chain = MagicMock()
    chain.get_height.return_value = local_h
    chain.get_state_root.return_value = "aa" * 32
    chain.get_block_by_hash = MagicMock(return_value=None)
    return P2PNode(cfg, chain, MagicMock())


def test_needles_v13166():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "handshake_head_without_height" in p2p
    assert "_handshake_head_without_height_refuse_reason" in p2p
    assert "native_handshake_head_requires_height" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "p2p_handshake_head_requires_height" in cfg
    assert "P2P_HANDSHAKE_HEAD_REQUIRES_HEIGHT" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.166.md").read_text(encoding="utf-8")
    assert "1.3.166-industrial" in notes
    assert Config().node_version.startswith("1.3.")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_handshake_head_requires_height" in metrics
    assert "abs_p2p_handshake_head_without_height_total" in metrics


def test_head_only_refused_when_local_tip():
    node = _node(local_h=10)
    assert (
        node._handshake_head_without_height_refuse_reason(DIGEST, 0, 10)
        == "handshake_head_without_height"
    )
    st = node.get_p2p_security_status()
    assert st.get("native_handshake_head_requires_height") is True


def test_head_only_allowed_at_genesis():
    node = _node(local_h=0)
    assert node._handshake_head_without_height_refuse_reason(DIGEST, 0, 0) == ""


def test_positive_height_ok():
    node = _node(local_h=10)
    assert node._handshake_head_without_height_refuse_reason(DIGEST, 10, 10) == ""


def test_disabled_skips():
    node = _node(local_h=10)
    node.config.p2p_handshake_head_requires_height = False
    assert node._handshake_head_without_height_refuse_reason(DIGEST, 0, 10) == ""
