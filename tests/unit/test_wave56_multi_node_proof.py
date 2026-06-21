"""Wave 56 — multi-node proof API and 3-validator rotation."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))
from wave_expect import EXPECTED_API_WAVE


class _FakeP2P:
    _state_consistent = True

    def get_peers_info(self):
        return [
            {"id": "p1", "host": "node2", "port": 5000, "height": 20, "head": "0x" + "aa" * 32},
            {"id": "p2", "host": "node3", "port": 5000, "height": 20, "head": "0x" + "aa" * 32},
        ]

    def peer_count(self):
        return 2


class _FakeCA:
    def get_attestations(self):
        return [{"validator": "0x" + "11" * 20, "target_height": 19}]

    def get_attestations_by_block(self):
        return [{"block_hash": "0x" + "aa" * 32, "votes": 2}]


class _FakeCAObserved:
    def __init__(self, validator):
        self.validator = validator

    def get_attestations(self):
        return [{"validator": self.validator, "target_height": 5}]

    def get_attestations_by_block(self):
        return [{"block_hash": "0x" + "aa" * 32, "votes": 2}]


class _FakeDB:
    def __init__(self, validators=None, stats=None):
        self._validators = validators or []
        self._stats = stats or []

    def get_validators(self):
        return self._validators

    def get_proposer_stats(self, limit=15):
        return self._stats[:limit]

    def get_state_root_mismatches(self, limit=20):
        return []

    def get_all_accounts(self):
        return [{"address": "0xabc"}]

    def get_total_supply(self):
        return 1_000_000.0

    def get_slash_events(self, limit=100):
        return []


class _FakeBC:
    def __init__(self, height=20):
        self._height = height

    def get_height(self):
        return self._height

    def get_state_root(self):
        return "0x" + "cc" * 32

    def get_last_block(self):
        return {"hash": "0x" + "aa" * 32, "state_root": "0x" + "cc" * 32}

    def get_state_root_policy(self):
        return {"strict": True}


class _FakeCfg3:
    node_id = "docker-node-1"
    chain_id = 77777
    miner_address = "0x" + "1".zfill(40)
    founder_address = ""
    testnet_expected_peers = 2
    testnet_expected_validators = 3
    testnet_validators_manifest = "docker/validators.devnet3.json"
    testnet_validator_index = 1
    max_supply = 221_000_000


def test_devnet3_manifest_entries():
    from runtime.devnet_validators import load_manifest, manifest_entries

    path = os.path.join(ROOT, "docker", "validators.devnet3.json")
    manifest = load_manifest(path)
    rows = manifest_entries(manifest, "0x" + "f" * 40)
    assert len(rows) == 3
    assert all(r.get("mines") for r in rows)


def test_multi_node_proof_healthy():
    from api.http import _build_testnet_multi_node_proof

    validators = [
        {"address": "0x" + hex(i)[2:].zfill(40), "active": True, "slashed": False}
        for i in range(3)
    ]
    stats = [
        {"proposer": validators[0]["address"], "blocks_proposed": 5},
        {"proposer": validators[1]["address"], "blocks_proposed": 4},
        {"proposer": validators[2]["address"], "blocks_proposed": 3},
    ]
    out = _build_testnet_multi_node_proof(
        _FakeP2P(),
        _FakeBC(20),
        _FakeCfg3(),
        _FakeDB(validators, stats),
        _FakeCA(),
    )
    assert out["api_wave"] == EXPECTED_API_WAVE
    assert out["proof_ok"] is True
    assert out["validators"]["distinct_proposers"] == 3
    assert out["attestations"]["count"] == 1


def test_multi_node_proof_counts_manifest_observed_validators():
    from api.http import _build_testnet_multi_node_proof

    validators = [
        {"address": "0x" + "1".zfill(40), "active": True, "slashed": False},
        {"address": "0x" + "2".zfill(40), "active": True, "slashed": False},
    ]
    observed = "0x" + "3".zfill(40)
    stats = [
        {"proposer": validators[0]["address"], "blocks_proposed": 3},
        {"proposer": validators[1]["address"], "blocks_proposed": 2},
        {"proposer": observed, "blocks_proposed": 1},
    ]
    out = _build_testnet_multi_node_proof(
        _FakeP2P(),
        _FakeBC(20),
        _FakeCfg3(),
        _FakeDB(validators, stats),
        _FakeCAObserved(observed),
    )
    assert out["validators"]["active_count"] == 2
    assert out["validators"]["effective_active_count"] == 3
    assert out["proof_ok"] is True


def test_validators_rotation_needs_three_for_devnet3():
    from api.http import _build_testnet_validators_status

    validators = [
        {"address": "0x" + hex(i)[2:].zfill(40), "active": True, "slashed": False}
        for i in range(3)
    ]
    stats = [{"proposer": validators[0]["address"], "blocks_proposed": 10}]
    out = _build_testnet_validators_status(
        _FakeDB(validators, stats), _FakeCfg3(), _FakeBC(20)
    )
    assert out["rotation_observed"] is False
    assert out["api_wave"] == EXPECTED_API_WAVE
