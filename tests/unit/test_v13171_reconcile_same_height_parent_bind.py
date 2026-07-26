#!/usr/bin/env python3
"""v1.3.171: same-height reconcile parent must match tip-height parent."""

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
TIP = "aa" * 32
PARENT = "11" * 32
WRONG_PARENT = "22" * 32


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
    chain = MagicMock()
    chain.get_height.return_value = 10
    chain.get_state_root.return_value = "ee" * 32
    chain.get_block_by_hash = MagicMock(return_value=None)
    chain.get_block = MagicMock(return_value={"hash": PARENT, "height": 9})
    chain.find_ancestor_height = MagicMock(return_value=9)
    node = P2PNode(cfg, chain, MagicMock())
    node.head = MagicMock(return_value=TIP)  # type: ignore[method-assign]
    node._ghost_canonical_head = MagicMock(return_value="")  # type: ignore
    return node


def test_needles_v13171():
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "reconcile_same_height_parent_mismatch" in p2p
    assert "_reconcile_same_height_parent_refuse_reason" in p2p
    assert "native_reconcile_same_height_parent_bind" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "p2p_reconcile_same_height_parent_bind" in cfg
    assert "P2P_RECONCILE_SAME_HEIGHT_PARENT_BIND" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.171.md").read_text(encoding="utf-8")
    assert "1.3.171-industrial" in notes
    assert Config().node_version.startswith("1.3.")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_reconcile_same_height_parent_bind" in metrics
    assert "abs_p2p_reconcile_same_height_parent_mismatch_total" in metrics


def test_refuse_wrong_parent():
    node = _node()
    assert (
        node._reconcile_same_height_parent_refuse_reason(
            {"hash": TARGET, "height": 10, "parent_hash": WRONG_PARENT}
        )
        == "reconcile_same_height_parent_mismatch"
    )


def test_ok_matching_parent():
    node = _node()
    assert (
        node._reconcile_same_height_parent_refuse_reason(
            {"hash": TARGET, "height": 10, "parent_hash": PARENT}
        )
        == ""
    )


def test_non_same_height_skips():
    node = _node()
    assert (
        node._reconcile_same_height_parent_refuse_reason(
            {"hash": TARGET, "height": 11, "parent_hash": WRONG_PARENT}
        )
        == ""
    )


@pytest.mark.asyncio
async def test_reconcile_aborts_on_parent_mismatch():
    node = _node()
    peer = PeerConnection(_FakeReader(), _FakeWriter())
    peer.peer_id = "rs1"
    peer.height = 10
    peer.head = TARGET
    node._request_block_by_hash = AsyncMock(  # type: ignore
        return_value={
            "hash": TARGET,
            "height": 10,
            "parent_hash": WRONG_PARENT,
        }
    )
    node._reorg_and_import_async = AsyncMock(return_value=True)  # type: ignore
    ok = await node._reconcile_to_head_hash(TARGET, peer)
    assert ok is False
    node._reorg_and_import_async.assert_not_called()
    assert node._reconcile_same_height_parent_mismatch_total >= 1
    st = node.get_p2p_security_status()
    assert st.get("native_reconcile_same_height_parent_bind") is True
