#!/usr/bin/env python3
"""Absolute mainnet v1 network constants — single source of truth."""

from __future__ import annotations

from crypto import native

DEVNET_CHAIN_ID = 77777
MAINNET_V1_CHAIN_ID = 778888


def ceremony_validator_address(chain_id: int, index: int, node_id: str) -> str:
    """Deterministic validator address for genesis ceremony templates."""
    seed = f"absolute-mainnet-v1|{int(chain_id)}|{int(index)}|{node_id}".encode("utf-8")
    digest = native.sha256_hex(seed)
    return "0x" + digest[:40]


def is_zero_prefix_placeholder_address(address: str) -> bool:
    raw = str(address or "").strip().lower().removeprefix("0x")
    if len(raw) != 40 or not all(c in "0123456789abcdef" for c in raw):
        return True
    return raw.startswith("0" * 38)


def is_repetitive_template_address(address: str) -> bool:
    """Detect obvious template fills (0xaaa…aaa1, 0xbbbb…, etc.)."""
    raw = str(address or "").strip().lower().removeprefix("0x")
    if len(raw) != 40 or not all(c in "0123456789abcdef" for c in raw):
        return True
    for ch in "0123456789abcdef":
        if raw.count(ch) >= 35:
            return True
    return False


def is_ceremony_template_address(address: str) -> bool:
    return is_zero_prefix_placeholder_address(address) or is_repetitive_template_address(address)
