#!/usr/bin/env python3
"""Tests for runtime.amount satoshi helpers."""

from decimal import Decimal

from runtime.amount import ABS_DECIMALS, SATOSHI_MULTIPLIER, from_satoshi, to_satoshi


def test_satoshi_round_trip_whole_abs():
    assert to_satoshi(1) == SATOSHI_MULTIPLIER
    assert from_satoshi(SATOSHI_MULTIPLIER) == Decimal("1")
    assert ABS_DECIMALS == 6


def test_to_satoshi_floors_dust():
    # 0.0000001 ABS -> 0 satoshi
    assert to_satoshi("0.0000001") == 0
    assert to_satoshi("1.9999999") == 1_999_999


def test_apply_delta_and_account_helpers():
    from runtime.amount import account_balance_abs, apply_delta_satoshi, dual_write_balance

    assert apply_delta_satoshi(1_000_000, -0.25) == 750_000
    row: dict = {}
    dual_write_balance(row, 2)
    assert account_balance_abs(row) == 2.0


def test_immutable_state_uses_shared_multiplier():
    from blockchain.immutable_state import SATOSHI_MULTIPLIER as ims_mult
    from runtime.amount import SATOSHI_MULTIPLIER as amt_mult

    assert ims_mult == amt_mult


def test_plan_transfer_fees_sat_is_integer_only():
    from runtime.amount import can_afford_transfer_sat, plan_transfer_fees_sat

    # 21000 * 1e-7 ABS = 0.0021 ABS = 2100 satoshi
    plan = plan_transfer_fees_sat(21000, 0.0000001, 0.5, 1.0)
    assert plan["fee_sat"] == 2100
    assert plan["burned_sat"] == 1050
    assert plan["miner_fee_sat"] == 1050
    assert plan["value_sat"] == 1_000_000
    assert plan["total_cost_sat"] == 1_002_100
    assert all(isinstance(v, int) for v in plan.values())
    assert can_afford_transfer_sat(1_002_100, plan["total_cost_sat"])
    assert not can_afford_transfer_sat(1_002_099, plan["total_cost_sat"])
