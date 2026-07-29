#!/usr/bin/env python3
"""Unit tests for ForkReconcileService (ADR 0005 same-height thin adapter)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sync.fork import (
    ForkPeerView,
    ForkReconcileConfig,
    ForkReconcilePolicy,
    ForkReconcileService,
    ForkReconcileStatus,
)
from tests.unit.fakes.fake_fork_io import FakeForkReconcileIO


PARENT = "parent_aa" * 4  # 64 hex-ish chars
LOCAL_TIP = "local_tip_hash_0001"
ALT_TIP = "alt_tip_hash_00002"


def _svc(io: FakeForkReconcileIO) -> ForkReconcileService:
    return ForkReconcileService(chain=io, fetch=io, probe=io, side=io)


def _peer(head: str = ALT_TIP, height: int = 5) -> ForkPeerView:
    return ForkPeerView(peer_id="peer-1", height=height, head_hash=head)


def _cfg(**kwargs) -> ForkReconcileConfig:
    base = dict(
        fork_probe_enabled=True,
        ghost_probe_enabled=False,
        prefer_ghost=False,
        head_hash_bind=True,
        contiguous_parent_bind=True,
        same_height_parent_bind=True,
        tip_head_bind=True,
    )
    base.update(kwargs)
    return ForkReconcileConfig(**base)


def test_policy_malicious_hash_mismatch() -> None:
    policy = ForkReconcilePolicy()
    bad = {"hash": "evil_hash", "height": 5, "parent_hash": PARENT}
    assert (
        policy.fetched_head_refuse_reason(ALT_TIP, bad, enabled=True)
        == "reconcile_head_hash_mismatch"
    )


def test_policy_same_height_parent_mismatch() -> None:
    policy = ForkReconcilePolicy()
    evil = {"hash": ALT_TIP, "height": 5, "parent_hash": "wrong_parent"}
    assert (
        policy.same_height_parent_refuse_reason(
            evil,
            tip_height=5,
            local_tip=LOCAL_TIP,
            local_parent=PARENT,
            enabled=True,
        )
        == "reconcile_same_height_parent_mismatch"
    )


def test_successful_same_height_sibling_reorg() -> None:
    alt = {"hash": ALT_TIP, "height": 5, "parent_hash": PARENT}
    io = FakeForkReconcileIO(
        height=5,
        head=LOCAL_TIP,
        expected_parent=PARENT,
        fetch_by_hash={ALT_TIP: alt},
        ancestors={PARENT: 4},
        tip_after_reorg=ALT_TIP,
    )
    out = _svc(io).run_same_height(_peer(), _cfg())
    assert out.status is ForkReconcileStatus.COMPLETE
    assert out.ok is True
    assert len(io.reorg_calls) == 1
    assert io.reorg_calls[0][0] == 4
    assert io.head() == ALT_TIP


def test_malicious_peer_hash_mismatch_refused() -> None:
    """Peer claims ALT_TIP but returns a body with a different hash."""
    evil_body = {"hash": "not_the_claimed_head", "height": 5, "parent_hash": PARENT}
    io = FakeForkReconcileIO(
        height=5,
        head=LOCAL_TIP,
        expected_parent=PARENT,
        fetch_by_hash={ALT_TIP: evil_body},
        ancestors={PARENT: 4},
    )
    out = _svc(io).run_same_height(_peer(), _cfg())
    assert out.status is ForkReconcileStatus.REFUSED
    assert out.reason_code == "reconcile_head_hash_mismatch"
    assert io.reorg_calls == []
    assert "reconcile_head_hash_mismatch" in io.refuses


def test_malicious_peer_wrong_parent_refused() -> None:
    """Same-height alternate with foreign parent — soft sibling bind refuse."""
    evil = {"hash": ALT_TIP, "height": 5, "parent_hash": "attacker_parent"}
    io = FakeForkReconcileIO(
        height=5,
        head=LOCAL_TIP,
        expected_parent=PARENT,
        fetch_by_hash={ALT_TIP: evil},
        ancestors={"attacker_parent": 3},
    )
    out = _svc(io).run_same_height(_peer(), _cfg())
    assert out.status is ForkReconcileStatus.REFUSED
    assert out.reason_code == "reconcile_same_height_parent_mismatch"
    assert io.reorg_calls == []


def test_fork_probe_refuse_short_circuit() -> None:
    io = FakeForkReconcileIO(
        height=5,
        head=LOCAL_TIP,
        fork_probe_refuse="fork_peer_head_hash_mismatch",
    )
    out = _svc(io).run_same_height(_peer(), _cfg())
    assert out.status is ForkReconcileStatus.REFUSED
    assert out.reason_code == "fork_peer_head_hash_mismatch"
    assert io.fetch_calls == []
    assert io.reorg_calls == []


def test_no_common_ancestor() -> None:
    alt = {"hash": ALT_TIP, "height": 5, "parent_hash": PARENT}
    io = FakeForkReconcileIO(
        height=5,
        head=LOCAL_TIP,
        expected_parent=PARENT,
        fetch_by_hash={ALT_TIP: alt},
        ancestors={},  # no ancestor
    )
    out = _svc(io).run_same_height(_peer(), _cfg())
    assert out.status is ForkReconcileStatus.NO_ANCESTOR
    assert io.reorg_calls == []


def test_import_failed() -> None:
    alt = {"hash": ALT_TIP, "height": 5, "parent_hash": PARENT}
    io = FakeForkReconcileIO(
        height=5,
        head=LOCAL_TIP,
        expected_parent=PARENT,
        fetch_by_hash={ALT_TIP: alt},
        ancestors={PARENT: 4},
        reorg_ok=False,
    )
    out = _svc(io).run_same_height(_peer(), _cfg())
    assert out.status is ForkReconcileStatus.IMPORT_FAILED


def test_tip_head_mismatch_after_import() -> None:
    alt = {"hash": ALT_TIP, "height": 5, "parent_hash": PARENT}
    io = FakeForkReconcileIO(
        height=5,
        head=LOCAL_TIP,
        expected_parent=PARENT,
        fetch_by_hash={ALT_TIP: alt},
        ancestors={PARENT: 4},
        tip_after_reorg="wrong_tip_after_import",
    )
    out = _svc(io).run_same_height(_peer(), _cfg())
    assert out.status is ForkReconcileStatus.REFUSED
    assert out.reason_code == "reconcile_tip_head_mismatch"


def test_skipped_when_same_head() -> None:
    io = FakeForkReconcileIO(height=5, head=LOCAL_TIP)
    out = _svc(io).run_same_height(_peer(head=LOCAL_TIP), _cfg())
    assert out.status is ForkReconcileStatus.SKIPPED
    assert out.ok is True


def test_fetch_failed() -> None:
    io = FakeForkReconcileIO(
        height=5,
        head=LOCAL_TIP,
        expected_parent=PARENT,
        fetch_by_hash={ALT_TIP: None},
    )
    out = _svc(io).run_same_height(_peer(), _cfg())
    assert out.status is ForkReconcileStatus.FETCH_FAILED


def test_no_network_imports_in_fork_domain() -> None:
    for rel in (
        "sync/fork/service.py",
        "sync/fork/policy.py",
        "sync/fork/types.py",
        "sync/fork/__init__.py",
    ):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "import network" not in src
        assert "from network" not in src


def test_p2p_thin_wire_needles() -> None:
    src = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "ForkReconcileService" in src
    assert "build_fork_reconcile_adapters" in src
    assert "svc.run_same_height" in src
    # Inline fetch loop evacuated from reconcile body.
    assert "Could not fetch head block" not in src
