"""Wave 54 — state consistency harness API."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)


class _FakeP2P:
    def __init__(self, peer_roots=None, consistent=True):
        self._peer_roots = peer_roots or []
        self._state_consistent = consistent

    def request_peer_state_roots_sync(self, timeout=8):
        return self._peer_roots


class _FakeBC:
    def __init__(self, height=5, live="0xlive", tip="0xlive"):
        self._height = height
        self._live = live
        self._tip = tip

    def get_height(self):
        return self._height

    def get_state_root(self):
        return self._live

    def get_last_block(self):
        return {"height": self._height, "state_root": self._tip, "hash": "0xabc"}

    def get_state_root_policy(self):
        return {"baseline_height": self._height, "verify_peer_state_root": True}


class _FakeDB:
    def get_state_root_mismatches(self, limit=20):
        return []

    def get_all_accounts(self):
        return [{"address": "0x1", "balance": 100.0, "nonce": 0}]

    def get_total_supply(self):
        return 1_000_000.0


class _FakeCfg:
    node_id = "test-node"
    chain_id = 77777
    max_supply = 221_000_000


def test_harness_healthy_aligned():
    from api.http import _build_state_consistency_harness

    root = "a" * 64
    p2p = _FakeP2P([{"peer_id": "p2", "height": 5, "state_root": root}])
    h = _build_state_consistency_harness(
        p2p, _FakeBC(live=root, tip=root), _FakeCfg(), _FakeDB()
    )
    assert h["harness_healthy"] is True
    assert h["tip_state_aligned"] is True
    assert h["api_wave"] == 57
    assert h["failed_checks"] == []


def test_harness_fails_tip_drift():
    from api.http import _build_state_consistency_harness

    p2p = _FakeP2P()
    h = _build_state_consistency_harness(
        p2p,
        _FakeBC(live="b" * 64, tip="a" * 64),
        _FakeCfg(),
        _FakeDB(),
    )
    assert h["harness_healthy"] is False
    assert "tip_state_aligned" in h["failed_checks"]


def test_harness_fails_peer_root_mismatch():
    from api.http import _build_state_consistency_harness

    local = "c" * 64
    p2p = _FakeP2P([{"peer_id": "p2", "height": 5, "state_root": "d" * 64}])
    h = _build_state_consistency_harness(
        p2p, _FakeBC(live=local, tip=local), _FakeCfg(), _FakeDB()
    )
    assert h["harness_healthy"] is False
    assert "peer_state_roots" in h["failed_checks"]
