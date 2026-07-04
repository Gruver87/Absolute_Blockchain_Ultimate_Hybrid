#!/usr/bin/env python3
"""verify_prod_consensus_mesh helper tests."""

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_p2p_ci as vpc


def test_verify_prod_consensus_mesh_ok():
    def fake_api(url):
        base = {
            "height": 5,
            "head_hash": "0x" + "ab" * 32,
            "consensus": {
                "mode": "unified",
                "unified_path": True,
                "lmd_ghost_enabled": True,
                "attestation_count": 2,
            },
        }
        return dict(base)

    with patch.object(vpc, "_api", side_effect=fake_api):
        assert vpc.verify_prod_consensus_mesh("http://n1", "http://n2") == 0


def test_verify_prod_consensus_mesh_rejects_head_mismatch():
    calls = {"n": 0}

    def fake_api(url):
        calls["n"] += 1
        head = "0x" + ("aa" if calls["n"] == 1 else "bb") * 32
        return {
            "height": 5,
            "head_hash": head,
            "consensus": {"mode": "unified", "unified_path": True},
        }

    with patch.object(vpc, "_api", side_effect=fake_api):
        assert vpc.verify_prod_consensus_mesh("http://n1", "http://n2") == 15
