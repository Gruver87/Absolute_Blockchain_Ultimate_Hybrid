#!/usr/bin/env python3
"""Versioned state-root encoding contract (tip vs storage truth)."""
from __future__ import annotations

import os
from typing import Any, Dict, List


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

# v2 — satoshi tip; activate only with ceremony flag (not silent switch on 778888).
STATE_ROOT_ENCODING_V2: Dict[str, Any] = {
    "version": 2,
    "name": "satoshi_b",
    "active": False,
    "payload_fields": ("a", "b_satoshi", "n", "c", "s"),
    "balance_field": "b_satoshi",
    "balance_unit": "satoshi_int",
    "satoshi_tip_ready": True,
    "note": (
        "Tip commits integer satoshi in b_satoshi. Requires ceremony rebuild + "
        "state_root_v2_ceremony_ok before activation."
    ),
}


def _ceremony_ok(config: Any = None) -> bool:
    if config is not None and bool(getattr(config, "state_root_v2_ceremony_ok", False)):
        return True
    return str(os.environ.get("ABS_STATE_ROOT_V2_CEREMONY_OK", "") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def requested_encoding_version(config: Any = None) -> int:
    if config is not None:
        return int(getattr(config, "state_root_encoding_version", 1) or 1)
    env = str(os.environ.get("ABS_STATE_ROOT_ENCODING_VERSION", "") or "").strip()
    if env.isdigit():
        return int(env)
    return 1


def active_state_root_encoding(config: Any = None) -> Dict[str, Any]:
    """Return the encoding used for consensus tip state_root commits."""
    requested = requested_encoding_version(config)
    if requested >= 2:
        if _ceremony_ok(config):
            return {**STATE_ROOT_ENCODING_V2, "active": True, "requested_version": requested}
        return {
            **STATE_ROOT_ENCODING_V2,
            "active": False,
            "requested_version": requested,
            "blocked_reason": (
                "state_root_encoding_version>=2 blocked until state_root_v2_ceremony_ok "
                "(or ABS_STATE_ROOT_V2_CEREMONY_OK=1)"
            ),
        }
    return dict(STATE_ROOT_ENCODING_V1)


def tip_encoding_version(config: Any = None) -> int:
    """Version actually used for tip hashing (1 unless v2 ceremony-armed)."""
    enc = active_state_root_encoding(config)
    if int(enc.get("version", 1) or 1) >= 2 and bool(enc.get("active")):
        return 2
    return 1


def account_tip_payload(row: dict, *, version: int = 1) -> Dict[str, Any]:
    """Build one account leaf for tip state_root (v1 float or v2 satoshi)."""
    from crypto.native import sha256_hex  # local import avoids cycles at module load

    code = row.get("code") or ""
    storage = row.get("storage") or "{}"
    code_hash = sha256_hex(code.encode()) if code else ""
    storage_hash = sha256_hex(storage.encode()) if storage else ""
    addr = row["address"]
    nonce = int(row["nonce"])
    if int(version) >= 2:
        if row.get("balance_satoshi") is not None:
            sat = max(0, int(row["balance_satoshi"]))
        else:
            sat = max(0, int(round(float(row.get("balance") or 0) * 1_000_000)))
        return {
            "a": addr,
            "b_satoshi": sat,
            "n": nonce,
            "c": code_hash,
            "s": storage_hash,
        }
    return {
        "a": addr,
        "b": round(float(row["balance"]), 12),
        "n": nonce,
        "c": code_hash,
        "s": storage_hash,
    }


def build_tip_payload(accounts: List[dict], *, version: int = 1) -> List[Dict[str, Any]]:
    return [account_tip_payload(row, version=version) for row in accounts]


def state_root_encoding_status(config: Any = None) -> Dict[str, Any]:
    """Honest encoding snapshot for /status and policy endpoints."""
    active = active_state_root_encoding(config)
    return {
        "active": active,
        "planned": dict(STATE_ROOT_ENCODING_V2),
        "storage_truth": "balance_satoshi_dual_write",
        "tip_version_live": tip_encoding_version(config),
    }
