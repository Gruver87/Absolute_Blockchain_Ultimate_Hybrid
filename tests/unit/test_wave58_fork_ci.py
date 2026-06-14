"""Wave 58 — fork recovery drill API and CI partition."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)


class _FakeP2P:
    _state_consistent = True

    def reconcile_peers_sync(self, timeout=90):
        return {"state_consistent": True, "height": 20, "reconciled": []}

    def get_peers_info(self):
        return [
            {"id": "p1", "host": "n2", "port": 5000, "height": 20, "head": "0x" + "aa" * 32},
        ]

    def peer_count(self):
        return 1


class _FakeBC:
    def get_height(self):
        return 20

    def get_state_root(self):
        return "0x" + "cc" * 32

    def get_last_block(self):
        return {"hash": "0x" + "aa" * 32, "state_root": "0x" + "cc" * 32}

    def ensure_state_at_tip(self):
        return True

    def get_state_root_policy(self):
        return {}


class _FakeCfg:
    node_id = "docker-node-1"
    chain_id = 77777
    testnet_expected_peers = 1
    max_supply = 221_000_000


class _FakeDB:
    def get_state_root_mismatches(self, limit=20):
        return []

    def get_all_accounts(self):
        return [{"address": "0xabc"}]

    def get_total_supply(self):
        return 1_000_000.0

    def get_slash_events(self, limit=100):
        return []


def test_fork_exercise_recovers():
    from api.http import _build_testnet_fork_exercise

    out = _build_testnet_fork_exercise(
        _FakeP2P(), _FakeBC(), _FakeCfg(), _FakeDB(), run_reconcile=True
    )
    assert out["api_wave"] == 58
    assert out["fork_recovered"] is True
    assert out["after"]["consensus_healthy"] is True


def test_fork_exercise_status_only():
    from api.http import _build_testnet_fork_exercise

    out = _build_testnet_fork_exercise(
        _FakeP2P(), _FakeBC(), _FakeCfg(), _FakeDB(), run_reconcile=False
    )
    assert out["fork_recovered"] is None
    assert out["run_reconcile"] is False
