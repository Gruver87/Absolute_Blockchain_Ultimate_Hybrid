#!/usr/bin/env python3
"""Unit tests for ForkReconcileService (ADR 0005 — fail-closed + Evidence)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sync.fork import (
    ForkPeerView,
    ForkReconcileConfig,
    ForkReconcileMaliciousError,
    ForkReconcilePolicy,
    ForkReconcileService,
    ForkReconcileStatus,
    ForkSecurityEvidence,
)
from tests.unit.fakes.fake_fork_io import FakeForkReconcileIO


PARENT = "parent_aa" * 4
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
    assert io.evidence == []
    assert io.strikes == []


def test_malicious_peer_hash_mismatch_fail_closed_with_evidence() -> None:
    """Peer claims ALT_TIP but returns a body with a different hash → raise + Evidence."""
    evil_body = {"hash": "not_the_claimed_head", "height": 5, "parent_hash": PARENT}
    io = FakeForkReconcileIO(
        height=5,
        head=LOCAL_TIP,
        expected_parent=PARENT,
        fetch_by_hash={ALT_TIP: evil_body},
        ancestors={PARENT: 4},
    )
    with pytest.raises(ForkReconcileMaliciousError) as ei:
        _svc(io).run_same_height(_peer(), _cfg())
    err = ei.value
    assert err.outcome.reason_code == "reconcile_head_hash_mismatch"
    assert isinstance(err.evidence, ForkSecurityEvidence)
    assert err.evidence.reason_code == "reconcile_head_hash_mismatch"
    assert err.evidence.peer_id == "peer-1"
    assert io.reorg_calls == []
    assert len(io.evidence) == 1
    assert io.strikes == [("peer-1", "reconcile_head_hash_mismatch")]
    payload = io.evidence[0].to_bus_payload()
    assert payload["fail_closed"] is True
    assert payload["kind"] == "fork_same_height_malicious"


def test_malicious_peer_wrong_parent_fail_closed() -> None:
    evil = {"hash": ALT_TIP, "height": 5, "parent_hash": "attacker_parent"}
    io = FakeForkReconcileIO(
        height=5,
        head=LOCAL_TIP,
        expected_parent=PARENT,
        fetch_by_hash={ALT_TIP: evil},
        ancestors={"attacker_parent": 3},
    )
    with pytest.raises(ForkReconcileMaliciousError) as ei:
        _svc(io).run_same_height(_peer(), _cfg())
    assert ei.value.outcome.reason_code == "reconcile_same_height_parent_mismatch"
    assert io.reorg_calls == []
    assert io.strikes
    assert io.evidence


def test_spam_fake_same_height_blocks_escalates_to_spam_evidence() -> None:
    """Repeated fake same-height bodies escalate to fork_same_height_spam."""
    evil_body = {"hash": "fake1", "height": 5, "parent_hash": PARENT}
    io = FakeForkReconcileIO(
        height=5,
        head=LOCAL_TIP,
        expected_parent=PARENT,
        fetch_by_hash={ALT_TIP: evil_body},
        ancestors={PARENT: 4},
    )
    svc = _svc(io)
    # Attempts 1 and 2: hash mismatch fail-closed.
    for _ in range(2):
        with pytest.raises(ForkReconcileMaliciousError) as ei:
            svc.run_same_height(_peer(), _cfg())
        assert ei.value.outcome.reason_code == "reconcile_head_hash_mismatch"
    # Attempt 3: spam escalate.
    with pytest.raises(ForkReconcileMaliciousError) as ei:
        svc.run_same_height(_peer(), _cfg())
    assert ei.value.outcome.reason_code == "fork_same_height_spam"
    assert ei.value.evidence.reason_code == "fork_same_height_spam"
    assert ei.value.evidence.attempt_count >= 3
    assert "fork_same_height_spam" in io.refuses
    assert io.reorg_calls == []
    assert len(io.evidence) == 3
    assert len(io.strikes) == 3


def test_fork_probe_malicious_fail_closed() -> None:
    io = FakeForkReconcileIO(
        height=5,
        head=LOCAL_TIP,
        fork_probe_refuse="fork_peer_head_hash_mismatch",
    )
    with pytest.raises(ForkReconcileMaliciousError) as ei:
        _svc(io).run_same_height(_peer(), _cfg())
    assert ei.value.outcome.reason_code == "fork_peer_head_hash_mismatch"
    assert io.fetch_calls == []
    assert io.evidence
    assert io.strikes


def test_no_common_ancestor() -> None:
    alt = {"hash": ALT_TIP, "height": 5, "parent_hash": PARENT}
    io = FakeForkReconcileIO(
        height=5,
        head=LOCAL_TIP,
        expected_parent=PARENT,
        fetch_by_hash={ALT_TIP: alt},
        ancestors={},
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


def test_tip_head_mismatch_after_import_soft_refuse() -> None:
    """Post-import tip mismatch is not in MALICIOUS set → soft REFUSED."""
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
    assert io.evidence == []


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


def test_tip_evidence_enforce_fail_closed() -> None:
    alt = {"hash": ALT_TIP, "height": 5, "parent_hash": PARENT}
    io = FakeForkReconcileIO(
        height=5,
        head=LOCAL_TIP,
        expected_parent=PARENT,
        fetch_by_hash={ALT_TIP: alt},
        ancestors={PARENT: 4},
        tip_evidence_refuse="parent_unknown",
    )
    with pytest.raises(ForkReconcileMaliciousError) as ei:
        _svc(io).run_same_height(_peer(), _cfg())
    assert ei.value.outcome.reason_code == "tip_evidence_enforce_refuse"
    assert io.reorg_calls == []
    assert io.evidence
    assert io.strikes


def test_no_network_imports_in_fork_domain() -> None:
    for rel in (
        "sync/fork/service.py",
        "sync/fork/policy.py",
        "sync/fork/types.py",
        "sync/fork/evidence.py",
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
    assert "ForkReconcileMaliciousError" in src
    assert "Could not fetch head block" not in src
    adapters = (ROOT / "network" / "fork_adapters.py").read_text(encoding="utf-8")
    assert "security.fork_refuse" in adapters
    assert "emit_security_evidence" in adapters
    assert "strike_malicious_peer" in adapters
