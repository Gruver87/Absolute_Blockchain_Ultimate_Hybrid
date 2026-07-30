# tests/unit/test_health_ready_adr0014.py — deep /health/ready helpers
"""Unit DoD for ADR 0014 deep readiness predicates (no live mesh required)."""

from __future__ import annotations

from types import SimpleNamespace

from api.http import (
    _deep_ready_mesh_checks,
    _quorum_height_aligned,
    _sync_engine_is_stalled,
    set_accepting_requests,
    is_accepting_requests,
)


def test_quorum_height_majority_within_gap():
    assert _quorum_height_aligned(10, [10, 10, 9]) is True
    assert _quorum_height_aligned(10, [10, 12, 15]) is False
    assert _quorum_height_aligned(10, []) is False


def test_sync_stalled_from_last_error():
    se = SimpleNamespace(get_status=lambda: {"last_sync_error": "fetch_stall"})
    assert _sync_engine_is_stalled(se) is True
    se2 = SimpleNamespace(get_status=lambda: {"last_sync_error": "", "sync_consistency_state": "ok"})
    assert _sync_engine_is_stalled(se2) is False


def test_deep_ready_requires_peers_and_quorum():
    class _P2P:
        def peer_count(self):
            return 2

        def get_peers_info(self):
            return [{"height": 5}, {"height": 5}]

    se = SimpleNamespace(get_status=lambda: {"last_sync_error": ""})
    deep = _deep_ready_mesh_checks(p2p=_P2P(), sync_engine=se, local_height=5)
    assert deep["peers_alive"] is True
    assert deep["sync_not_stalled"] is True
    assert deep["quorum_height"] is True


def test_accepting_requests_flag_roundtrip():
    set_accepting_requests(False)
    assert is_accepting_requests() is False
    set_accepting_requests(True)
    assert is_accepting_requests() is True
