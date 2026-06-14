"""Wave 55 — 5-validator devnet manifest and API."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)


class _FakeDB:
    def __init__(self, validators=None, stats=None):
        self._validators = validators or []
        self._stats = stats or []

    def get_validators(self):
        return self._validators

    def get_proposer_stats(self, limit=15):
        return self._stats[:limit]


class _FakeBC:
    def get_height(self):
        return 20


class _FakeCfg:
    node_id = "docker-node-1"
    chain_id = 77777
    testnet_expected_validators = 5
    testnet_validators_manifest = "docker/validators.devnet5.json"
    testnet_validator_index = 1


def test_manifest_resolves_addresses():
    from runtime.devnet_validators import load_manifest, manifest_entries

    path = os.path.join(ROOT, "docker", "validators.devnet5.json")
    manifest = load_manifest(path)
    rows = manifest_entries(manifest, "0x" + "f" * 40)
    assert len(rows) == 5
    assert rows[0]["address"] == "0x" + "f" * 40
    assert rows[1]["address"].startswith("0x")
    assert rows[1]["address"] != rows[0]["address"]


def test_validators_api_healthy():
    from api.http import _build_testnet_validators_status

    validators = [{"address": "0x" + hex(i)[2:].zfill(40), "active": True, "slashed": False} for i in range(5)]
    stats = [
        {"proposer": validators[0]["address"], "blocks_proposed": 5},
        {"proposer": validators[1]["address"], "blocks_proposed": 3},
        {"proposer": validators[2]["address"], "blocks_proposed": 2},
    ]
    out = _build_testnet_validators_status(_FakeDB(validators, stats), _FakeCfg(), _FakeBC())
    assert out["validators_healthy"] is True
    assert out["rotation_observed"] is True
    assert out["api_wave"] == 59


def test_validators_api_unhealthy_count():
    from api.http import _build_testnet_validators_status

    validators = [{"address": "0xabc", "active": True, "slashed": False}]
    out = _build_testnet_validators_status(_FakeDB(validators), _FakeCfg(), _FakeBC())
    assert out["validators_healthy"] is False
