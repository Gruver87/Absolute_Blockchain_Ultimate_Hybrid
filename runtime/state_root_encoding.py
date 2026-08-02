#!/usr/bin/env python3
"""Versioned state-root encoding contract (tip vs storage truth)."""
from __future__ import annotations

import contextvars
import os
from typing import Any, Dict, List, Optional


# v1 — legacy float tip (kept for offline/historical roots only).
STATE_ROOT_ENCODING_V1: Dict[str, Any] = {
    "version": 1,
    "name": "float_b_round12",
    "active": False,
    "payload_fields": ("a", "b", "n", "c", "s"),
    "balance_field": "b",
    "balance_unit": "abs_float_round12",
    "satoshi_tip_ready": False,
    "note": (
        "Legacy tip used native float round(balance,12) field \"b\". "
        "Wave C tip+apply cutover uses v2 satoshi when ceremony-armed."
    ),
}

# v2 — integer satoshi tip (live when ceremony-armed).
STATE_ROOT_ENCODING_V2: Dict[str, Any] = {
    "version": 2,
    "name": "satoshi_b",
    "active": False,
    "payload_fields": ("a", "b_satoshi", "n", "c", "s"),
    "balance_field": "b_satoshi",
    "balance_unit": "satoshi_int",
    "satoshi_tip_ready": True,
    "note": (
        "Tip commits integer satoshi in b_satoshi (SATOSHI_MULTIPLIER=1e6). "
        "Requires state_root_encoding_version>=2 and state_root_v2_ceremony_ok."
    ),
}

# Bound by AbsoluteNode / Blockchain so tip hashing sees node config (not only env).
# ContextVar covers asyncio tasks; process-global covers P2P worker threads (Wave C).
_tip_config_ctx: contextvars.ContextVar[Optional[Any]] = contextvars.ContextVar(
    "abs_tip_encoding_config", default=None
)
_tip_config_global: Optional[Any] = None


def bind_tip_encoding_config(config: Any) -> contextvars.Token:
    """Bind config for tip_encoding_version() when callers omit config."""
    global _tip_config_global
    _tip_config_global = config
    return _tip_config_ctx.set(config)


def reset_tip_encoding_config(token: contextvars.Token) -> None:
    _tip_config_ctx.reset(token)


def clear_tip_encoding_config() -> None:
    """Clear process-global tip config (tests)."""
    global _tip_config_global
    _tip_config_global = None


def _resolve_config(config: Any = None) -> Any:
    if config is not None:
        return config
    bound = _tip_config_ctx.get()
    if bound is not None:
        return bound
    return _tip_config_global


def _ceremony_ok(config: Any = None) -> bool:
    cfg = _resolve_config(config)
    if cfg is not None and bool(getattr(cfg, "state_root_v2_ceremony_ok", False)):
        return True
    return str(os.environ.get("ABS_STATE_ROOT_V2_CEREMONY_OK", "") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def requested_encoding_version(config: Any = None) -> int:
    cfg = _resolve_config(config)
    if cfg is not None:
        return int(getattr(cfg, "state_root_encoding_version", 1) or 1)
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
    return {**STATE_ROOT_ENCODING_V1, "active": True, "requested_version": requested}


def tip_encoding_version(config: Any = None) -> int:
    """Version actually used for tip hashing (1 unless v2 ceremony-armed)."""
    enc = active_state_root_encoding(config)
    if int(enc.get("version", 1) or 1) >= 2 and bool(enc.get("active")):
        return 2
    return 1


def account_tip_payload(row: dict, *, version: int = 1) -> Dict[str, Any]:
    """Build one account leaf for tip state_root (v1 float or v2 satoshi)."""
    from crypto.native import sha256_hex  # local import avoids cycles at module load
    from runtime.amount import SATOSHI_MULTIPLIER, account_satoshi

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
            sat = max(0, account_satoshi(row))
        return {
            "a": addr,
            "b_satoshi": sat,
            "n": nonce,
            "c": code_hash,
            "s": storage_hash,
        }
    # Legacy v1 — display-scale float tip only (not used when ceremony-armed).
    _ = SATOSHI_MULTIPLIER
    return {
        "a": addr,
        "b": round(float(row.get("balance") or 0), 12),
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
