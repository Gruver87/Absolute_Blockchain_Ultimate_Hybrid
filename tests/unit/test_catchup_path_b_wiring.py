#!/usr/bin/env python3
"""Integration tests for Step B: P2P adapter → CatchUpPathAService wiring.

No live TCP. Peer is simulated in-process via asyncio Futures; the adapter
bridges them synchronously into the domain service just as the real adapter
does under ``_sync_with_peer``.
"""

from __future__ import annotations

import asyncio
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from network.catchup_adapters import (
    CatchUpP2PChainAdapter,
    CatchUpP2PFetchAdapter,
    CatchUpP2PProbeAdapter,
    CatchUpP2PSideEffectAdapter,
    build_path_a_adapters,
)
from sync.catchup import (
    CatchUpConfig,
    CatchUpOrchestrator,
    CatchUpPathAService,
    CatchUpPeerView,
    CatchUpStatus,
)


# ── Minimal fake P2P node ─────────────────────────────────────────────────────


class _FakeBlockchain:
    def __init__(self, height: int = 0) -> None:
        self._height = height
        self._blocks: Dict[int, dict] = {}
        self._by_hash: Dict[str, dict] = {}

    def get_height(self) -> int:
        return self._height

    def get_block(self, h: int) -> Optional[dict]:
        return self._blocks.get(int(h))

    def get_block_by_hash(self, hh: str) -> Optional[dict]:
        return self._by_hash.get(str(hh or ""))

    def import_block(self, data: dict) -> bool:
        h = int(data.get("height", -1) or -1)
        if h < 0:
            return False
        self._blocks[h] = data
        self._by_hash[str(data.get("hash") or "")] = data
        self._height = max(self._height, h)
        return True

    def reorg_to_ancestor(self, h: int) -> bool:
        self._height = int(h)
        return True


class _FakeConfig:
    sync_batch_size = 2
    p2p_catch_up_require_head = True
    p2p_catch_up_tip_head_bind = True
    p2p_catch_up_height_continuity_bind = True
    p2p_catch_up_contiguous_parent_bind = True
    p2p_catch_up_tip_probe = False
    p2p_catch_up_peer_head_probe = False


class _FakePeer:
    def __init__(self, height: int, head: str, peer_id: str = "peer-sim") -> None:
        self.height = int(height)
        self.head = str(head or "")
        self.peer_id = str(peer_id or "peer-sim")
        self._sends: List[tuple] = []

    async def send(self, msg_type: str, data: Any) -> None:
        self._sends.append((msg_type, data))


class _FakeP2PNode:
    """Minimal P2PNode surface for adapter tests (no TCP, no asyncio server)."""

    def __init__(self, blockchain: _FakeBlockchain, config: _FakeConfig) -> None:
        self.blockchain = blockchain
        self.config = config
        self._running = True
        self.refuse_counts: Dict[str, int] = {}
        self.import_fails: List[str] = []
        self._sync_fail = 0

    def head(self) -> str:
        bc = self.blockchain
        tip = bc._blocks.get(bc.get_height())
        if isinstance(tip, dict):
            return str(tip.get("hash") or "")
        return ""

    def get_block(self, h: Any) -> Any:
        if isinstance(h, int):
            return self.blockchain._blocks.get(h)
        return self.blockchain._by_hash.get(str(h or ""))

    def import_block(self, data: dict) -> bool:
        return self.blockchain.import_block(data)

    def _expected_parent_for_height(self, height: int) -> str:
        h = int(height)
        if h <= 0:
            return "0" * 64
        prev = self.blockchain._blocks.get(h - 1)
        if isinstance(prev, dict):
            return str(prev.get("hash") or "")
        return "0" * 64

    def _bump_catch_up_refuse(self, reason: str) -> None:
        r = str(reason or "")
        self.refuse_counts[r] = self.refuse_counts.get(r, 0) + 1

    def _note_peer_import_fail(self, peer: Any) -> None:
        self.import_fails.append(str(getattr(peer, "peer_id", "?") or "?"))

    async def _catch_up_local_tip_probe_refuse_reason(self, peer: Any) -> str:
        if not getattr(self.config, "p2p_catch_up_tip_probe", False):
            return ""
        return ""

    async def _catch_up_peer_head_probe_refuse_reason(self, peer: Any) -> str:
        if not getattr(self.config, "p2p_catch_up_peer_head_probe", False):
            return ""
        return ""

    async def _wait_peer_response(
        self,
        peer: Any,
        expected_types: tuple,
        timeout: float = 30,
        presend=None,
        request_ctx: Optional[dict] = None,
    ) -> Optional[dict]:
        if presend:
            await presend()
        resp = getattr(peer, "_next_response", None)
        if resp is None:
            return None
        if callable(resp):
            return resp(request_ctx)
        return resp


# ── Helper ────────────────────────────────────────────────────────────────────


def _blk(h: int, parent: str, digest: str) -> dict:
    return {"height": h, "parent_hash": parent, "hash": digest}


def _run_sync_in_loop(
    svc: CatchUpPathAService,
    peer_view: CatchUpPeerView,
    cfg: CatchUpConfig,
) -> "CatchUpStatus":
    """Run ``run_ahead`` synchronously (used from tests that already set up adapters)."""
    return svc.run_ahead(peer_view, cfg).status


def _make_svc_and_peer(
    blockchain: _FakeBlockchain,
    peer: _FakePeer,
    loop: asyncio.AbstractEventLoop,
    config: Optional[_FakeConfig] = None,
) -> tuple[CatchUpPathAService, CatchUpPeerView, CatchUpConfig]:
    cfg = config or _FakeConfig()
    p2p = _FakeP2PNode(blockchain, cfg)
    chain_a, fetch_a, probe_a, side_a = build_path_a_adapters(p2p, peer, loop)
    svc = CatchUpPathAService(chain=chain_a, fetch=fetch_a, probe=probe_a, side=side_a)
    peer_view = CatchUpPeerView(
        peer_id=peer.peer_id,
        height=peer.height,
        head_hash=peer.head,
    )
    catch_up_cfg = CatchUpConfig(
        batch_size=cfg.sync_batch_size,
        require_head=cfg.p2p_catch_up_require_head,
        tip_head_bind=cfg.p2p_catch_up_tip_head_bind,
        height_continuity_bind=cfg.p2p_catch_up_height_continuity_bind,
        contiguous_parent_bind=cfg.p2p_catch_up_contiguous_parent_bind,
        tip_probe_enabled=cfg.p2p_catch_up_tip_probe,
        peer_head_probe_enabled=cfg.p2p_catch_up_peer_head_probe,
        fetch_timeout=5.0,
    )
    return svc, peer_view, catch_up_cfg


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_adapter_refuse_no_head() -> None:
    """Adapter plumbs ahead_refuse → service returns REFUSED without any fetch."""
    loop = asyncio.new_event_loop()
    bc = _FakeBlockchain(height=2)
    bc._blocks[2] = _blk(2, "00" * 32, "tip2" * 8)
    peer = _FakePeer(height=5, head="", peer_id="p-no-head")
    svc, pv, cfg = _make_svc_and_peer(bc, peer, loop)
    try:
        result = loop.run_until_complete(asyncio.to_thread(svc.run_ahead, pv, cfg))
    finally:
        loop.close()
    assert result.status is CatchUpStatus.REFUSED
    assert result.reason_code == "catch_up_no_head"


def test_adapter_successful_multi_batch_import() -> None:
    """Simulated peer delivers two batches; service reaches target height."""
    b3 = _blk(3, "tip2" * 8, "b3" * 16)
    b4 = _blk(4, "b3" * 16, "b4" * 16)
    b5 = _blk(5, "b4" * 16, "b5" * 16)

    call_seq = [[b3, b4], [b5]]
    call_idx = [0]

    def _respond(ctx: Optional[dict]) -> dict:
        i = call_idx[0]
        call_idx[0] += 1
        if i >= len(call_seq):
            return None
        return {"type": "blocks", "data": call_seq[i]}

    loop = asyncio.new_event_loop()
    bc = _FakeBlockchain(height=2)
    bc._blocks[2] = _blk(2, "00" * 32, "tip2" * 8)
    peer = _FakePeer(height=5, head="b5" * 16, peer_id="p-multi")
    peer._next_response = _respond
    svc, pv, cfg = _make_svc_and_peer(bc, peer, loop)
    try:
        result = loop.run_until_complete(asyncio.to_thread(svc.run_ahead, pv, cfg))
    finally:
        loop.close()
    assert result.status is CatchUpStatus.COMPLETE
    assert result.reached_target is True
    assert result.imported == 3
    assert bc.get_height() == 5


def test_adapter_stall_on_timeout() -> None:
    """Peer returns None (timeout); service emits STALLED."""
    loop = asyncio.new_event_loop()
    bc = _FakeBlockchain(height=1)
    bc._blocks[1] = _blk(1, "00" * 32, "tip1" * 8)
    peer = _FakePeer(height=4, head="bb" * 32, peer_id="p-stall")
    peer._next_response = None  # always times out
    svc, pv, cfg = _make_svc_and_peer(bc, peer, loop)
    try:
        result = loop.run_until_complete(asyncio.to_thread(svc.run_ahead, pv, cfg))
    finally:
        loop.close()
    assert result.status is CatchUpStatus.STALLED


def test_adapter_height_continuity_refuse_aborts() -> None:
    """Body at wrong height triggers refuse inside service via adapter."""
    bad = _blk(9, "tip2" * 8, "wrong" * 6)  # expects 3

    loop = asyncio.new_event_loop()
    bc = _FakeBlockchain(height=2)
    bc._blocks[2] = _blk(2, "00" * 32, "tip2" * 8)
    peer = _FakePeer(height=5, head="aa" * 32, peer_id="p-cont")
    peer._next_response = {"type": "blocks", "data": [bad]}
    svc, pv, cfg = _make_svc_and_peer(bc, peer, loop)
    try:
        result = loop.run_until_complete(asyncio.to_thread(svc.run_ahead, pv, cfg))
    finally:
        loop.close()
    assert result.status is CatchUpStatus.INCOMPLETE
    assert bc.get_height() == 2  # nothing imported


def test_adapter_tip_head_mismatch_at_target() -> None:
    """Block at peer.height has hash ≠ peer.head → incomplete."""
    b3 = _blk(3, "tip2" * 8, "actual_hash" * 4)  # hash ≠ peer.head

    loop = asyncio.new_event_loop()
    bc = _FakeBlockchain(height=2)
    bc._blocks[2] = _blk(2, "00" * 32, "tip2" * 8)
    peer = _FakePeer(height=3, head="expected_hash" * 4, peer_id="p-tiphd")
    peer._next_response = {"type": "blocks", "data": [b3]}
    svc, pv, cfg = _make_svc_and_peer(bc, peer, loop)
    try:
        result = loop.run_until_complete(asyncio.to_thread(svc.run_ahead, pv, cfg))
    finally:
        loop.close()
    assert result.status is CatchUpStatus.INCOMPLETE


def test_adapter_probe_port_returns_no_refuse_by_default() -> None:
    """With probes disabled, service skips probes and proceeds to import."""
    b3 = _blk(3, "tip2" * 8, "b3" * 16)

    loop = asyncio.new_event_loop()
    bc = _FakeBlockchain(height=2)
    bc._blocks[2] = _blk(2, "00" * 32, "tip2" * 8)
    peer = _FakePeer(height=3, head="b3" * 16, peer_id="p-probe")
    peer._next_response = {"type": "blocks", "data": [b3]}
    # probes disabled in _FakeConfig (tip_probe=False, peer_head_probe=False)
    svc, pv, cfg = _make_svc_and_peer(bc, peer, loop)
    try:
        result = loop.run_until_complete(asyncio.to_thread(svc.run_ahead, pv, cfg))
    finally:
        loop.close()
    assert result.status is CatchUpStatus.COMPLETE
    assert bc.get_height() == 3


def test_adapter_side_effect_bump_refuse_routes_to_p2p() -> None:
    """SideEffect adapter correctly routes bump_refuse to P2PNode counters."""
    loop = asyncio.new_event_loop()
    bc = _FakeBlockchain(height=2)
    bc._blocks[2] = _blk(2, "00" * 32, "tip2" * 8)
    peer = _FakePeer(height=5, head="", peer_id="p-side")
    cfg_obj = _FakeConfig()
    p2p = _FakeP2PNode(bc, cfg_obj)
    _, _, _, side_a = build_path_a_adapters(p2p, peer, loop)
    side_a.bump_refuse("catch_up_no_head")
    side_a.bump_refuse("catch_up_no_head")
    loop.close()
    assert p2p.refuse_counts.get("catch_up_no_head", 0) == 2


def test_chain_adapter_import_delegates_to_p2p() -> None:
    """Chain adapter import_block calls P2PNode.import_block (tip-safety path)."""
    loop = asyncio.new_event_loop()
    bc = _FakeBlockchain(height=0)
    peer = _FakePeer(height=1, head="b1" * 32)
    cfg_obj = _FakeConfig()
    p2p = _FakeP2PNode(bc, cfg_obj)
    chain_a, _, _, _ = build_path_a_adapters(p2p, peer, loop)
    blk = _blk(1, "00" * 32, "b1" * 32)
    ok = chain_a.import_block(blk)
    loop.close()
    assert ok is True
    assert bc.get_height() == 1


def test_no_network_imports_in_adapters() -> None:
    """Adapter module must not import sync domain types at module level."""
    src = (ROOT / "network" / "catchup_adapters.py").read_text(encoding="utf-8")
    # Only allowed network import is the module itself being in network/.
    assert "from sync.catchup" not in src
    assert "from sync.ports" not in src
    assert "from sync.consistency" not in src
    # But P2P message constants are allowed (defined locally in the adapter).
    assert "_MSG_GET_BLOCKS" in src
