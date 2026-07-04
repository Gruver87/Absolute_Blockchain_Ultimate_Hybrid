#!/usr/bin/env python3
"""Ceremony keygen and wallet binding tests."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.ceremony_keygen import (
    generate_validator_set,
    validate_manifest_public_keys,
    verify_ceremony_directory,
    verify_wallet_file,
    wallet_matches_manifest_row,
)


def test_wallet_matches_manifest_row_ok():
    row = {
        "index": 1,
        "address": "0xabc",
        "public_key": "deadbeef",
        "mines": True,
    }
    wallet = {"address": "0xabc", "public_key": "deadbeef"}
    ok, reason = wallet_matches_manifest_row(wallet, row)
    assert ok is True
    assert reason == ""


def test_wallet_matches_manifest_row_address_mismatch():
    row = {"index": 1, "address": "0xabc", "public_key": "", "mines": True}
    wallet = {"address": "0xdef", "public_key": ""}
    ok, reason = wallet_matches_manifest_row(wallet, row)
    assert ok is False
    assert "address_mismatch" in reason


def test_validate_manifest_public_keys_requires_mining():
    manifest = {
        "validators": [
            {"index": 1, "address": "0xaaa", "mines": True, "public_key": "", "stake": 1000},
        ]
    }
    errors = validate_manifest_public_keys(manifest, require_mining_keys=True)
    assert any("mining_validator_missing_public_key" in e for e in errors)


def test_generate_and_verify_ceremony_directory(tmp_path):
    template = {
        "version": 1,
        "validators": [
            {
                "index": 1,
                "node_id": "v1",
                "address": "0x0000000000000000000000000000000000000001",
                "mines": True,
                "stake": 5000,
                "shard_id": 0,
            },
            {
                "index": 2,
                "node_id": "v2",
                "address": "0x0000000000000000000000000000000000000002",
                "mines": True,
                "stake": 3000,
                "shard_id": 0,
            },
        ],
    }
    template_path = tmp_path / "template.json"
    template_path.write_text(json.dumps(template), encoding="utf-8")
    out_dir = tmp_path / "ceremony"
    _manifest, _errors, manifest_path = generate_validator_set(str(template_path), str(out_dir))
    errors, _warnings = verify_ceremony_directory(str(out_dir))
    assert errors == [], errors
    assert manifest_path.is_file()
    ok, reason = verify_wallet_file(
        str(out_dir / "wallets" / "validator-1.wallet.json"),
        str(manifest_path),
        1,
    )
    assert ok is True, reason
