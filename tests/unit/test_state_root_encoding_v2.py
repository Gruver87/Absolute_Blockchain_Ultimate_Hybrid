# tests/unit/test_state_root_encoding_v2.py
"""Satoshi tip encoding activates only with ceremony arming."""

from __future__ import annotations

from types import SimpleNamespace

from crypto.native import _python_state_root_from_accounts
from runtime.state_root_encoding import (
    account_tip_payload,
    active_state_root_encoding,
    tip_encoding_version,
)


def test_v1_default_tip_payload_has_float_b():
    row = {"address": "a1", "balance": 1.5, "nonce": 0, "code": "", "storage": "{}"}
    tip = account_tip_payload(row, version=1)
    assert tip["b"] == 1.5
    assert "b_satoshi" not in tip


def test_v2_tip_payload_uses_satoshi():
    row = {
        "address": "a1",
        "balance": 1.5,
        "balance_satoshi": 1_500_000,
        "nonce": 0,
        "code": "",
        "storage": "{}",
    }
    tip = account_tip_payload(row, version=2)
    assert tip["b_satoshi"] == 1_500_000
    assert "b" not in tip


def test_v2_blocked_without_ceremony():
    cfg = SimpleNamespace(state_root_encoding_version=2, state_root_v2_ceremony_ok=False)
    enc = active_state_root_encoding(cfg)
    assert enc["active"] is False
    assert tip_encoding_version(cfg) == 1


def test_v2_active_with_ceremony_changes_root():
    cfg = SimpleNamespace(state_root_encoding_version=2, state_root_v2_ceremony_ok=True)
    assert tip_encoding_version(cfg) == 2
    accounts = [
        {
            "address": "z",
            "balance": 2.0,
            "balance_satoshi": 2_000_000,
            "nonce": 1,
            "code": "",
            "storage": "{}",
        }
    ]
    r1 = _python_state_root_from_accounts(accounts, encoding_version=1)
    r2 = _python_state_root_from_accounts(accounts, encoding_version=2)
    assert r1 != r2
    assert len(r2) == 64
