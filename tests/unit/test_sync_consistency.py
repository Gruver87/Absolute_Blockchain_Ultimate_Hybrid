#!/usr/bin/env python3
"""Unit tests for sync consistency machine / service (ADR 0003)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sync.consistency import (
    ConsistencyMachine,
    ConsistencyService,
    ConsistencyState,
    InMemoryConsistencyStore,
    PeerSyncView,
    WireProbeResult,
)


def test_boot_unknown_not_green() -> None:
    m = ConsistencyMachine()
    snap = m.boot_snapshot(now=1.0)
    d = m.decide_from_snapshot(snap)
    assert snap.state is ConsistencyState.UNKNOWN
    assert snap.consistent is False
    assert d.trusted is False
    assert d.may_mine is False


def test_incomplete_ahead_is_behind_open_not_trusted() -> None:
    m = ConsistencyMachine()
    cur = m.boot_snapshot(now=1.0)
    peers = [PeerSyncView(peer_id="p1", height=20, head_hash="aa" * 32)]
    probe = WireProbeResult.succeeded(
        wire_roots=({"peer_id": "p1", "height": 20, "state_root": "bb" * 32},)
    )
    # local height 10, peer root at height 20 — no same-height match, peers ahead
    snap, decision = m.evaluate_probe(
        cur,
        peers=peers,
        local_height=10,
        local_root="cc" * 32,
        probe=probe,
        now=2.0,
    )
    assert snap.state is ConsistencyState.BEHIND_OPEN
    assert snap.consistent is False
    assert decision.trusted is False
    assert decision.may_catch_up is True


def test_same_height_match_consistent() -> None:
    m = ConsistencyMachine()
    cur = m.boot_snapshot(now=1.0)
    root = "dd" * 32
    peers = [PeerSyncView(peer_id="p1", height=5, head_hash="aa" * 32)]
    probe = WireProbeResult.succeeded(
        wire_roots=({"peer_id": "p1", "height": 5, "state_root": root},)
    )
    snap, decision = m.evaluate_probe(
        cur,
        peers=peers,
        local_height=5,
        local_root=root,
        probe=probe,
        now=2.0,
    )
    assert snap.state is ConsistencyState.CONSISTENT
    assert snap.consistent is True
    assert decision.trusted is True
    assert decision.may_mine is True


def test_mismatch_lockdown() -> None:
    m = ConsistencyMachine()
    cur = m.boot_snapshot(now=1.0)
    peers = [PeerSyncView(peer_id="peer-abc", height=5)]
    probe = WireProbeResult.succeeded(
        wire_roots=({"peer_id": "peer-abc", "height": 5, "state_root": "11" * 32},)
    )
    snap, decision = m.evaluate_probe(
        cur,
        peers=peers,
        local_height=5,
        local_root="22" * 32,
        probe=probe,
        now=2.0,
    )
    assert snap.state is ConsistencyState.LOCKED_DOWN
    assert snap.reason_code == "state_root_mismatch"
    assert decision.may_catch_up is False
    assert snap.lockdown_total >= 1


def test_probe_fail_lockdown() -> None:
    m = ConsistencyMachine()
    cur = m.boot_snapshot(now=1.0)
    peers = [PeerSyncView(peer_id="p1", height=1)]
    snap, _ = m.evaluate_probe(
        cur,
        peers=peers,
        local_height=1,
        local_root="00" * 32,
        probe=WireProbeResult.failed("timeout"),
        now=2.0,
    )
    assert snap.state is ConsistencyState.LOCKED_DOWN


def test_service_apply_and_status() -> None:
    store = InMemoryConsistencyStore()
    svc = ConsistencyService(store)
    peers = [PeerSyncView(peer_id="p1", height=1)]
    root = "aa" * 32
    d = svc.apply_probe_evaluation(
        peers=peers,
        local_height=1,
        local_root=root,
        probe=WireProbeResult.succeeded(
            wire_roots=({"peer_id": "p1", "height": 1, "state_root": root},)
        ),
    )
    assert d.trusted is True
    st = svc.status()
    assert st["consistency_boundary"] is True
    assert st["state_consistent"] is True
    assert st["sync_consistency_state"] == "consistent"


def test_sync_engine_incomplete_ahead_returns_false() -> None:
    from sync.sync_engine import SyncEngine

    class _BC:
        def get_state_root(self):
            return "aa" * 32

        def get_height(self):
            return 10

    class _Peer:
        peer_id = "p1"
        height = 50
        head = "bb" * 32

    class _Node:
        blockchain = _BC()
        peers = {"p1": _Peer()}

        def request_peer_state_roots_sync(self):
            return [{"peer_id": "p1", "height": 50, "state_root": "cc" * 32}]

    eng = SyncEngine(node=_Node())
    ok = eng.sync_state()
    assert ok is False
    assert eng.consistency.snapshot().state is ConsistencyState.BEHIND_OPEN
