#!/usr/bin/env python3
"""Canonical ABS amount helpers (satoshi / micro-ABS).

Canonical money unit for new storage writes is integer satoshi
(1 ABS = 1_000_000). Float ABS remains on the wire / legacy columns for
compatibility; dual-write keeps ``balance`` (float) derived from satoshi.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_DOWN, InvalidOperation
from typing import Any, Dict, Mapping, MutableMapping, Optional, Union

# 1 ABS = 1_000_000 satoshi (same as USDC-style micro units)
ABS_DECIMALS = 6
SATOSHI_MULTIPLIER = 10 ** ABS_DECIMALS

NumberLike = Union[int, float, str, Decimal]


def to_satoshi(amount_abs: NumberLike) -> int:
    """Convert ABS amount to integer satoshi (floor toward zero)."""
    if isinstance(amount_abs, bool):
        raise TypeError("bool is not a valid amount")
    try:
        from crypto import native

        if native.native_available() and hasattr(native, "amount_to_satoshi"):
            if isinstance(amount_abs, int):
                return int(native.amount_to_satoshi(str(amount_abs)))
            if isinstance(amount_abs, Decimal):
                return int(native.amount_to_satoshi(format(amount_abs, "f")))
            return int(native.amount_to_satoshi(str(amount_abs)))
    except Exception:
        pass
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
    """Display / legacy float ABS — prefer from_satoshi for money math."""
    try:
        from crypto import native

        if native.native_available() and hasattr(native, "amount_from_satoshi_float"):
            return float(native.amount_from_satoshi_float(int(satoshi)))
    except Exception:
        pass
    return float(from_satoshi(satoshi))


def account_satoshi(row: Optional[Mapping[str, Any]]) -> int:
    """Read satoshi from account row; backfill from float balance if needed."""
    if not row:
        return 0
    if row.get("balance_satoshi") is not None:
        try:
            return max(0, int(row["balance_satoshi"]))
        except (TypeError, ValueError):
            pass
    return max(0, to_satoshi(row.get("balance", 0) or 0))


def account_balance_abs(row: Optional[Mapping[str, Any]]) -> float:
    """ABS float derived from satoshi when present."""
    return from_satoshi_float(account_satoshi(row))


def dual_write_balance(row: MutableMapping[str, Any], balance_abs: NumberLike) -> Dict[str, Any]:
    """Set balance_satoshi + derived float balance on an account dict."""
    sat = max(0, to_satoshi(balance_abs))
    row["balance_satoshi"] = sat
    row["balance"] = from_satoshi_float(sat)
    return dict(row)


def apply_delta_satoshi(current_sat: int, delta_abs: NumberLike) -> int:
    """Apply ABS delta to satoshi balance (never negative)."""
    try:
        from crypto import native

        if native.native_available() and hasattr(native, "amount_apply_delta_satoshi"):
            if isinstance(delta_abs, bool):
                raise TypeError("bool is not a valid amount")
            if isinstance(delta_abs, Decimal):
                delta_s = format(delta_abs, "f")
            else:
                delta_s = str(delta_abs)
            return int(native.amount_apply_delta_satoshi(int(current_sat), delta_s))
    except TypeError:
        raise
    except Exception:
        pass
    return max(0, int(current_sat) + to_satoshi(delta_abs))


def plan_transfer_fees(
    gas: int,
    gas_price_wei: float,
    burn_rate: float,
    value: float = 0.0,
    gas_used: Optional[int] = None,
) -> Dict[str, float]:
    """Split L1 transfer fee into fee/burned/miner_fee/total_cost (ABS floats)."""
    try:
        from crypto import native

        if native.native_available() and hasattr(native, "plan_transfer_fees"):
            fee, burned, miner_fee, total_cost = native.plan_transfer_fees(
                int(gas),
                float(gas_price_wei),
                float(burn_rate),
                float(value),
                int(gas_used) if gas_used is not None else None,
            )
            return {
                "fee": float(fee),
                "burned": float(burned),
                "miner_fee": float(miner_fee),
                "total_cost": float(total_cost),
            }
    except Exception:
        pass
    fee = float(gas) * float(gas_price_wei)
    if gas_used is not None:
        fee = max(fee, float(gas_used) * float(gas_price_wei))
    rate = max(0.0, min(1.0, float(burn_rate)))
    burned = fee * rate
    miner_fee = fee - burned
    return {
        "fee": fee,
        "burned": burned,
        "miner_fee": miner_fee,
        "total_cost": float(value) + fee,
    }


def can_afford_transfer(sender_sat: int, total_cost_abs: NumberLike) -> bool:
    """True if sender satoshi balance covers ABS total cost."""
    try:
        from crypto import native

        if native.native_available() and hasattr(native, "can_afford_transfer"):
            return bool(native.can_afford_transfer(int(sender_sat), float(total_cost_abs)))
    except Exception:
        pass
    return int(sender_sat) >= to_satoshi(total_cost_abs)
