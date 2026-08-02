#!/usr/bin/env python3
"""Canonical ABS amount helpers (satoshi / micro-ABS).

Canonical money unit for new storage writes is integer satoshi
(1 ABS = 1_000_000). Float ABS remains on the wire / legacy columns for
compatibility; dual-write keeps ``balance`` (float) derived from satoshi.
"""
from __future__ import annotations

import logging
import os
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from typing import Any, Dict, Mapping, MutableMapping, Optional, Union

# 1 ABS = 1_000_000 satoshi (same as USDC-style micro units)
ABS_DECIMALS = 6
SATOSHI_MULTIPLIER = 10 ** ABS_DECIMALS

NumberLike = Union[int, float, str, Decimal]
logger = logging.getLogger("amount")
_native_fallback_warned = False


def _native_required() -> bool:
    """Fail-closed when prod-canonical ABS_REQUIRE_NATIVE_CRYPTO is set (v1.3.65)."""
    for key in ("ABS_REQUIRE_NATIVE_CRYPTO", "REQUIRE_NATIVE_CRYPTO"):
        if os.environ.get(key, "").strip().lower() in ("1", "true", "yes", "on"):
            return True
    return False


def _native_fallback(op: str, exc: BaseException) -> None:
    global _native_fallback_warned
    if _native_required():
        raise RuntimeError(f"native amount op {op} required but failed: {exc}") from exc
    if not _native_fallback_warned:
        _native_fallback_warned = True
        logger.warning(
            "[amount] native %s failed; using Python fallback (further falls suppressed): %s",
            op,
            exc,
        )


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
    except Exception as exc:
        _native_fallback("amount_to_satoshi", exc)
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
    except Exception as exc:
        _native_fallback("amount_from_satoshi_float", exc)
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
    """Apply ABS delta to satoshi balance (never negative — clamps)."""
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
    except Exception as exc:
        _native_fallback("amount_apply_delta_satoshi", exc)
    return max(0, int(current_sat) + to_satoshi(delta_abs))


def try_debit_satoshi(current_sat: int, debit_abs: NumberLike) -> int:
    """Debit ABS amount from satoshi; raise on underflow (v1.3.68 — no silent clamp)."""
    if isinstance(debit_abs, bool):
        raise TypeError("bool is not a valid amount")
    debit = to_satoshi(debit_abs)
    if debit < 0:
        raise ValueError("debit must be non-negative")
    cur = int(current_sat)
    if cur < debit:
        raise ValueError(f"insufficient_balance: have={cur} need={debit}")
    return cur - debit


def plan_transfer_fees_sat(
    gas: int,
    gas_price_wei: NumberLike,
    burn_rate: NumberLike,
    value: NumberLike = 0,
    gas_used: Optional[int] = None,
) -> Dict[str, int]:
    """Split L1 transfer fee into satoshi ints (Wave C tip+apply hot path)."""
    try:
        from crypto import native

        if native.native_available() and hasattr(native, "plan_transfer_fees_satoshi"):
            fee_s, burned_s, miner_s, total_s = native.plan_transfer_fees_satoshi(
                int(gas),
                str(gas_price_wei),
                str(burn_rate),
                str(value),
                int(gas_used) if gas_used is not None else None,
            )
            value_s = to_satoshi(value)
            return {
                "fee_sat": int(fee_s),
                "burned_sat": int(burned_s),
                "miner_fee_sat": int(miner_s),
                "value_sat": value_s,
                "total_cost_sat": int(total_s),
            }
    except Exception as exc:
        _native_fallback("plan_transfer_fees_satoshi", exc)
    gp = Decimal(str(gas_price_wei))
    if gp < 0:
        raise ValueError("negative gas_price_wei")
    fee_abs = Decimal(int(gas)) * gp
    if gas_used is not None:
        fee_abs = max(fee_abs, Decimal(int(gas_used)) * gp)
    fee_sat = to_satoshi(fee_abs)
    rate = Decimal(str(burn_rate))
    if rate < 0:
        rate = Decimal("0")
    if rate > 1:
        rate = Decimal("1")
    burned_sat = int((Decimal(fee_sat) * rate).to_integral_value(rounding=ROUND_DOWN))
    miner_fee_sat = fee_sat - burned_sat
    value_sat = to_satoshi(value)
    return {
        "fee_sat": fee_sat,
        "burned_sat": burned_sat,
        "miner_fee_sat": miner_fee_sat,
        "value_sat": value_sat,
        "total_cost_sat": value_sat + fee_sat,
    }


def plan_transfer_fees(
    gas: int,
    gas_price_wei: float,
    burn_rate: float,
    value: float = 0.0,
    gas_used: Optional[int] = None,
) -> Dict[str, float]:
    """Display/legacy ABS floats — prefer plan_transfer_fees_sat for apply math."""
    sat = plan_transfer_fees_sat(gas, gas_price_wei, burn_rate, value, gas_used=gas_used)
    return {
        "fee": from_satoshi_float(sat["fee_sat"]),
        "burned": from_satoshi_float(sat["burned_sat"]),
        "miner_fee": from_satoshi_float(sat["miner_fee_sat"]),
        "total_cost": from_satoshi_float(sat["total_cost_sat"]),
    }


def can_afford_transfer_sat(sender_sat: int, total_cost_sat: int) -> bool:
    """True if sender satoshi covers integer total cost."""
    return int(sender_sat) >= max(0, int(total_cost_sat))


def can_afford_transfer(sender_sat: int, total_cost_abs: NumberLike) -> bool:
    """True if sender satoshi balance covers ABS total cost (edge helper)."""
    try:
        from crypto import native

        if native.native_available() and hasattr(native, "can_afford_transfer"):
            return bool(native.can_afford_transfer(int(sender_sat), float(total_cost_abs)))
    except Exception as exc:
        _native_fallback("can_afford_transfer", exc)
    return can_afford_transfer_sat(int(sender_sat), to_satoshi(total_cost_abs))


def apply_satoshi_delta(current_sat: int, delta_sat: int) -> int:
    """Apply integer satoshi delta; never negative."""
    return max(0, int(current_sat) + int(delta_sat))
