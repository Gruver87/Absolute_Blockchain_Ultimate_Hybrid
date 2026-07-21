#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rust amount kernels + StateEngine batch apply parity."""

import json

import pytest

from crypto import native
from execution.state_engine import StateEngine
from runtime.amount import apply_delta_satoshi, from_satoshi_float, to_satoshi


def test_amount_to_satoshi_matches_python_contract():
    assert native.amount_to_satoshi("1") == 1_000_000
    assert native.amount_to_satoshi("0.0000001") == 0
    assert native.amount_to_satoshi("1.9999999") == 1_999_999
    assert to_satoshi("1.5") == native.amount_to_satoshi("1.5")


def test_amount_apply_delta_satoshi_never_negative():
    assert native.amount_apply_delta_satoshi(1_000_000, "-0.25") == 750_000
    assert apply_delta_satoshi(1_000_000, -0.25) == 750_000
    assert native.amount_apply_delta_satoshi(100, "-1") == 0


def test_amount_from_satoshi_float_parity():
    assert abs(native.amount_from_satoshi_float(1_500_000) - 1.5) < 1e-12
    assert abs(from_satoshi_float(1_500_000) - 1.5) < 1e-12


def test_state_engine_apply_transactions_matches_engine():
    eng = StateEngine()
    eng.create_genesis({"alice": 100, "bob": 0})
    before = {
        addr: {"balance": int(acc.balance), "nonce": int(acc.nonce)}
        for addr, acc in eng.state.accounts.items()
    }
    txs = [{"from": "alice", "to": "bob", "amount": 10, "fee": 1, "nonce": 0}]
    applied = json.loads(
        native.state_engine_apply_transactions(
            json.dumps(before, separators=(",", ":")),
            json.dumps(txs, separators=(",", ":")),
        )
    )
    eng.transition(
        {
            "number": 1,
            "hash": "h1",
            "parent_hash": "g",
            "timestamp": 1,
            "transactions": txs,
        }
    )
    assert applied["bob"]["balance"] == eng.get_balance_satoshi("bob")
    assert applied["alice"]["balance"] == eng.get_balance_satoshi("alice")
    assert applied["alice"]["nonce"] == 1


def test_state_engine_apply_rejects_insufficient_balance():
    if not native.native_available():
        return
    accounts = {"alice": {"balance": 100, "nonce": 0}}
    txs = [{"from": "alice", "to": "bob", "amount": 1, "fee": 0, "nonce": 0}]
    with pytest.raises(RuntimeError, match="Insufficient balance"):
        native.state_engine_apply_transactions(
            json.dumps(accounts),
            json.dumps(txs),
        )


def test_native_state_engine_rejects_too_many_txs():
    if not native.native_available():
        return
    import abs_native

    accounts = "{}"
    txs = json.dumps([{"from": "a", "to": "b", "amount": 0, "nonce": 0}] * 100_001)
    with pytest.raises(ValueError, match="too_many_txs"):
        abs_native.state_engine_apply_transactions(accounts, txs)


def test_plan_transfer_fees_matches_python_float_math():
    from runtime.amount import plan_transfer_fees

    gas, price, burn, value = 21_000, 0.000_000_1, 0.02, 1.0
    plan = plan_transfer_fees(gas, price, burn, value)
    fee = gas * price
    assert abs(plan["fee"] - fee) < 1e-15
    assert abs(plan["burned"] - fee * burn) < 1e-15
    assert abs(plan["miner_fee"] - (fee - fee * burn)) < 1e-15
    assert abs(plan["total_cost"] - (value + fee)) < 1e-15

    plan2 = plan_transfer_fees(gas, price, burn, value, gas_used=50_000)
    assert abs(plan2["fee"] - 50_000 * price) < 1e-15


def test_can_afford_transfer_uses_satoshi_floor():
    from runtime.amount import can_afford_transfer, to_satoshi

    cost = 1.5
    need = to_satoshi(cost)
    assert can_afford_transfer(need, cost) is True
    assert can_afford_transfer(need - 1, cost) is False
