#!/usr/bin/env python3
"""Canonical ABS amount helpers (satoshi / micro-ABS).

Wire and SQLite account balances historically use float ABS.
ImmutableStateManager and validators use integer satoshi (1 ABS = 1_000_000).
This module is the single conversion surface for new code paths.
Full DB INTEGER migration is a later wave — do not invent a second float ledger.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_DOWN, InvalidOperation
from typing import Union

# 1 ABS = 1_000_000 satoshi (same as USDC-style micro units)
ABS_DECIMALS = 6
SATOSHI_MULTIPLIER = 10 ** ABS_DECIMALS

NumberLike = Union[int, float, str, Decimal]


def to_satoshi(amount_abs: NumberLike) -> int:
    """Convert ABS amount to integer satoshi (floor toward zero)."""
    if isinstance(amount_abs, bool):
        raise TypeError("bool is not a valid amount")
    try:
        d = Decimal(str(amount_abs))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"invalid amount: {amount_abs!r}") from exc
    scaled = (d * Decimal(SATOSHI_MULTIPLIER)).quantize(
        Decimal("1"), rounding=ROUND_DOWN
    )
    return int(scaled)


def from_satoshi(satoshi: int) -> Decimal:
    """Convert satoshi int to Decimal ABS (exact)."""
    return Decimal(int(satoshi)) / Decimal(SATOSHI_MULTIPLIER)


def from_satoshi_float(satoshi: int) -> float:
    """Display helper — prefer from_satoshi for money math."""
    return float(from_satoshi(satoshi))
