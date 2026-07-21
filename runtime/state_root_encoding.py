#!/usr/bin/env python3
"""Versioned state-root encoding contract (tip vs storage truth)."""
from __future__ import annotations

from typing import Any, Dict

# v1 — live consensus tip (soak contract; industrial_gate enforces float "b" path).
STATE_ROOT_ENCODING_V1: Dict[str, Any] = {
    "version": 1,
    "name": "float_b_round12",
    "active": True,
    "payload_fields": ("a", "b", "n", "c", "s"),
    "balance_field": "b",
    "balance_unit": "abs_float_round12",
    "satoshi_tip_ready": False,
    "note": (
        "Consensus tip uses native float round(balance,12) encoding. "
        "balance_satoshi dual-write is storage/read truth only until a versioned migration. "
        "See docs/STATE_ROOT_ENCODING_MIGRATION.md."
    ),
}

# v2 — planned; not active on mainnet-v1 without ceremony rebuild.
STATE_ROOT_ENCODING_V2: Dict[str, Any] = {
    "version": 2,
    "name": "satoshi_b",
    "active": False,
    "payload_fields": ("a", "b_satoshi", "n", "c", "s"),
    "balance_field": "b_satoshi",
    "balance_unit": "satoshi_int",
    "satoshi_tip_ready": True,
    "note": "Scaffold only — requires chain halt + genesis/ceremony rebuild before activation.",
}


def active_state_root_encoding(config: Any = None) -> Dict[str, Any]:
    """Return the encoding used for consensus tip state_root commits."""
    requested = int(getattr(config, "state_root_encoding_version", 1) or 1) if config else 1
    if requested >= 2:
        # Fail closed: v2 is not live until explicitly enabled after migration.
        return {
            **STATE_ROOT_ENCODING_V2,
            "active": False,
            "requested_version": requested,
            "blocked_reason": "state_root_encoding_version>=2 not activated (ceremony migration required)",
        }
    return dict(STATE_ROOT_ENCODING_V1)


def state_root_encoding_status(config: Any = None) -> Dict[str, Any]:
    """Honest encoding snapshot for /status and policy endpoints."""
    active = active_state_root_encoding(config)
    return {
        "active": active,
        "planned": dict(STATE_ROOT_ENCODING_V2),
        "storage_truth": "balance_satoshi_dual_write",
    }
