#!/usr/bin/env python3
"""Ceremony deploy to data/ tests."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.ceremony_deploy import deploy_ceremony_files
from runtime.ceremony_keygen import generate_validator_set


def test_deploy_ceremony_files_copies_manifest_and_wallet(tmp_path):
    template = {
        "version": 1,
        "validators": [
            {
                "index": 1,
                "node_id": "v1",
                "address": "0x0000000000000000000000000000000000000001",
                "mines": True,
                "stake": 5000,
            }
        ],
    }
    template_path = tmp_path / "template.json"
    template_path.write_text(json.dumps(template), encoding="utf-8")
    ceremony_dir = tmp_path / "ceremony"
    generate_validator_set(str(template_path), str(ceremony_dir))

    cfg = tmp_path / "node.json"
    cfg.write_text(
        json.dumps(
            {
                "network_name": "Test",
                "chain_id": 778888,
                "deployment_mode": "prod",
                "validators_manifest_path": "data/validators.manifest.json",
            }
        ),
        encoding="utf-8",
    )
    data_dir = tmp_path / "data"
    result, errors = deploy_ceremony_files(
        str(ceremony_dir),
        root=tmp_path,
        data_dir=str(data_dir),
        node_config=str(cfg.name),
    )
    assert errors == [], errors
    assert (data_dir / "validators.manifest.json").is_file()
    assert (data_dir / "wallet.json").is_file()
    assert result.get("ceremony_hash")
