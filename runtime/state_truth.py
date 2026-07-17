#!/usr/bin/env python3
"""Canonical balance reads — prefer satoshi dual-write when present."""
from __future__ import annotations

from typing import Any

from runtime.amount import from_satoshi_float, to_satoshi


def canonical_balance_satoshi(store: Any, address: str) -> int:
    """Integer satoshi from DB/Rocks/Hybrid (or float ABS fallback)."""
    if store is None:
        return 0
    if hasattr(store, "get_balance_satoshi"):
        try:
            return max(0, int(store.get_balance_satoshi(address)))
        except Exception:
            pass
    if hasattr(store, "get_balance"):
        try:
            return max(0, to_satoshi(store.get_balance(address)))
        except Exception:
            return 0
    return 0


def canonical_balance_abs(store: Any, address: str) -> float:
    """ABS float derived from canonical satoshi."""
    return from_satoshi_float(canonical_balance_satoshi(store, address))
