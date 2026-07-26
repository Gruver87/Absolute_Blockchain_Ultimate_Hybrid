#!/usr/bin/env python3
"""v1.3.173: after reconcile import, tip hash must match target_head."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from network.p2p_node import P2PNode, PeerConnection
from runtime.config import Config

TARGET = "ab" * 32
WRONG_TIP = "aa" * 32
PARENT = "11" * 32


class _FakeWriter:
    def write(self, _data):
        return None

    async def drain(self):
        return None

    def close(self):
        return None

    def get_extra_info(self, _name, default=None):
        return default

    def is_closing(self):
        return False


class _FakeReader:
    async def read(self, _n):
        await asyncio.sleep(0)
        return b""


def _node() -> P2PNode:
    cfg = Config()
    cfg.p2p_native_transport = False
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.bootstrap_peers = []
    cfg.p2p_reconcile_head_hash_bind = True
    cfg.p2p_reconcile_contiguous_parent_bind = True
    cfg.p2p_reconcile_same_height_parent_bind = True
    cfg.p2p_reconcile_tip_head_bind = True
    chain = MagicMock()
    chain.get_height.return_value = 10
    chain.get_state_root.return_value = "ee" * 32
    chain.get_block_by_hash = MagicMock(return_value=None)
    chain.get_block = MagicMock(return_value={"hash": PARENT, "height": 9})
    chain.find_ancestor_height = MagicMock(return_value=9)
    node = P2PNode(cfg, chain, MagicMock())
    node.head = MagicMock(return_value=WRONG_TIP)  # type: ignore[method-assign]
    node._ghost_canonical_head = MagicMock(return_value="")  # type: ignore
    return node


def test_needles_v13173():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "reconcile_tip_head_mismatch" in p2p
    assert "_reconcile_tip_head_refuse_reason" in p2p
    assert "native_reconcile_tip_head_bind" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "p2p_reconcile_tip_head_bind" in cfg
    assert "P2P_RECONCILE_TIP_HEAD_BIND" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.173.md").read_text(encoding="utf-8")
    assert "1.3.173-industrial" in notes
    assert Config().node_version.startswith("1.3.173")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_reconcile_tip_head_bind" in metrics
    assert "abs_p2p_reconcile_tip_head_mismatch_total" in metrics


def test_refuse_tip_mismatch():
    node = _node()
    assert node._reconcile_tip_head_refuse_reason(TARGET) == "reconcile_tip_head_mismatch"


def test_ok_matching_tip():
    node = _node()
    node.head = MagicMock(return_value=TARGET)  # type: ignore[method-assign]
    assert node._reconcile_tip_head_refuse_reason(TARGET) == ""


def test_empty_tip_skips():
    node = _node()
    node.head = MagicMock(return_value="")  # type: ignore[method-assign]
    assert node._reconcile_tip_head_refuse_reason(TARGET) == ""


@pytest.mark.asyncio
async def test_reconcile_aborts_on_post_import_tip_mismatch():
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "rs1"
    peer.height = 10
    peer.head = TARGET
    node._request_block_by_hash = AsyncMock(  # type: ignore
        return_value={
            "hash": TARGET,
            "height": 10,
            "parent_hash": PARENT,
        }
    )
    node._reorg_and_import_async = AsyncMock(return_value=True)  # type: ignore
    # tip stays wrong after "successful" import
    node.head = MagicMock(return_value=WRONG_TIP)  # type: ignore[method-assign]
    ok = await node._reconcile_to_head_hash(TARGET, peer)
    assert ok is False
    assert node._reconcile_tip_head_mismatch_total >= 1
    st = node.get_p2p_security_status()
    assert st.get("native_reconcile_tip_head_bind") is True
    assert int(st.get("reconcile_tip_head_mismatch_total", 0) or 0) >= 1
