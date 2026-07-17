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


def test_immutable_state_uses_shared_multiplier():
    from blockchain.immutable_state import SATOSHI_MULTIPLIER as ims_mult
    from runtime.amount import SATOSHI_MULTIPLIER as amt_mult

    assert ims_mult == amt_mult
