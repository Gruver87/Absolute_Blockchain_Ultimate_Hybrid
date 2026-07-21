#!/usr/bin/env python3
"""v1.3.44: native EVM host-in-apply fee effects."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crypto import native


def test_native_host_effects_symbol():
    assert native.native_available()
    assert hasattr(native, "blockchain_apply_host_effects")


def test_host_effects_fee_only_and_reward():
    accounts = {
        "0xsender": {"balance": 10_000_000, "nonce": 0},
        "0xminer": {"balance": 0, "nonce": 0},
        "0xburn": {"balance": 0, "nonce": 0},
    }
    effects = [
        {
            "from": "0xsender",
            "to": "0xcontract",
            "value": 1.0,
            "apply_value": False,
            "gas": 21000,
            "gas_used": 21000,
            "nonce": 0,
        }
    ]
    raw = native.blockchain_apply_host_effects(
        json.dumps(accounts),
        json.dumps(effects),
        1e-9,
        0.5,
        "0xminer",
        "0xburn",
        1.0,
        10_000_000,
        100_000_000,
    )
    out = json.loads(raw)
    assert out.get("host_effects") is True
    assert out.get("evm") is True
    acc = out["accounts"]
    assert int(acc["0xsender"]["nonce"]) == 1
    assert int(acc["0xsender"]["balance"]) < 10_000_000
    assert int(acc["0xminer"]["balance"]) > 0
    assert int(out.get("reward_sat", 0)) > 0


def test_wiring():
    text = Path("core/blockchain.py").read_text(encoding="utf-8")
    assert "blockchain_apply_host_effects" in text
    assert "_apply_evm_host_block_native" in text
    assert "_block_transactions_are_all_evm" in text
    assert "def blockchain_apply_host_effects" in Path("crypto/native.py").read_text(
        encoding="utf-8"
    )
