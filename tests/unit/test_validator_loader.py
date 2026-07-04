#!/usr/bin/env python3
"""Public validator manifest loader and registry merge."""
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)


class _FakeConsensus:
    def __init__(self):
        self.validators = {}

    def add_validator(self, address, stake):
        self.validators[address] = stake


class _FakeDB:
    def __init__(self, validators=None):
        self._validators = list(validators or [])
        self.saved = []

    def get_validators(self, active_only=True):
        return list(self._validators)

    def save_validator(self, address, stake):
        self.saved.append((address, stake))
        self._validators.append({"address": address, "stake": stake, "active": True})


class _FakeRegistry:
    def __init__(self):
        self.validators = {}
        self.registered = []

    def register_validator(self, address, stake):
        self.registered.append((address, stake))
        self.validators[address] = type("VS", (), {"to_dict": lambda self: {"address": address, "stake": stake}})()


class _FakeNode:
    def __init__(self, prod=False):
        self.config = type("Cfg", (), {"is_production": lambda self: prod, "min_stake": 1000})()
        self.consensus = _FakeConsensus()
        self.db = _FakeDB()
        self.validator_registry = _FakeRegistry()


def _write_manifest(tmpdir, validators):
    path = os.path.join(tmpdir, "validators.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "validators": validators}, f)
    return path


def test_snapshot_public_set_addresses_only():
    from runtime.validator_loader import load_manifest, snapshot_public_set

    path = os.path.join(ROOT, "validators.manifest.example.json")
    manifest = load_manifest(path)
    rows = snapshot_public_set(manifest)
    assert len(rows) == 3
    assert rows[0]["address"].startswith("0x")
    assert rows[0]["source"] == "manifest"
    assert "private_key" not in rows[0]


def test_manifest_requires_runtime_key_derivation():
    from runtime.validator_loader import manifest_requires_runtime_key_derivation

    dev = {"validators": [{"index": 1, "stake": 1000}]}
    prod = {"validators": [{"address": "0x" + "a" * 40, "stake": 1000}]}
    assert manifest_requires_runtime_key_derivation(dev) is True
    assert manifest_requires_runtime_key_derivation(prod) is False


def test_apply_public_manifest_registers_db_and_registry():
    from runtime.validator_loader import apply_public_manifest

    with tempfile.TemporaryDirectory() as tmp:
        path = _write_manifest(
            tmp,
            [
                {"index": 1, "address": "0x" + "1" * 40, "stake": 5000},
                {"index": 2, "address": "0x" + "2" * 40, "stake": 3000},
            ],
        )
        node = _FakeNode()
        added = apply_public_manifest(node, path)
        assert added == 2
        assert len(node.db.saved) == 2
        assert len(node.validator_registry.registered) == 2
        assert node._public_validator_manifest == path
        assert len(node._public_validator_set) == 2


def test_apply_public_manifest_blocks_dev_derivation_in_prod():
    from runtime.validator_loader import apply_public_manifest

    with tempfile.TemporaryDirectory() as tmp:
        path = _write_manifest(tmp, [{"index": 1, "stake": 1000}])
        node = _FakeNode(prod=True)
        try:
            apply_public_manifest(node, path)
            assert False, "expected RuntimeError"
        except RuntimeError as exc:
            assert "explicit 0x addresses" in str(exc)


def test_merged_registry_view_from_parts():
    from runtime.validator_loader import merged_registry_view_from_parts

    db = _FakeDB(
        [{"address": "0x" + "1" * 40, "stake": 5000, "active": True}],
    )
    manifest_rows = [
        {
            "index": 2,
            "node_id": "v2",
            "address": "0x" + "2" * 40,
            "stake": 3000,
            "mines": True,
            "public_key": "",
            "source": "manifest",
        }
    ]
    registry = _FakeRegistry()
    registry.register_validator("0x" + "1" * 40, 5000)

    view = merged_registry_view_from_parts(
        db, registry, manifest_rows, "validators.manifest.example.json"
    )
    assert view["enabled"] is True
    assert view["count"] == 2
    assert view["manifest_path"] == "validators.manifest.example.json"
    addrs = {v["address"].lower() for v in view["validators"]}
    assert "0x" + "1" * 40 in addrs
    assert "0x" + "2" * 40 in addrs
