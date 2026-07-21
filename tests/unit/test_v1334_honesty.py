#!/usr/bin/env python3
"""v1.3.34 honesty: Rust L1 status/event bind, lock verify, atomic debit/refund."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_rust_verifies_lock_and_receipt_status():
    text = Path("bridge/rust_bridge/src/main.rs").read_text(encoding="utf-8")
    assert "receipt_status_ok" in text
    assert '"lock" | "bridge"' in text
    assert "BRIDGE_REQUIRE_L1_EVENT" in text
    assert "receipt_has_contract_log" in text
    assert "abs_bridge_bin_v5" in text


def test_confirm_lock_passes_to_chain():
    text = Path("bridge/abs_bridge.py").read_text(encoding="utf-8")
    assert '"to_chain": self._normalize_chain(lock.get("to_chain", ""))' in text
    assert "debit_and_create_bridge_lock" in text
    assert "refund_pending_bridge_lock" in text
    assert "BRIDGE_L1_LOCK_CONTRACT" in text
    assert "l1_event_abi_decoded" in text
    assert "event_binding_mode" in text


def test_storage_atomic_bridge_lock_apis():
    db = Path("storage/database.py").read_text(encoding="utf-8")
    assert "def debit_and_create_bridge_lock" in db
    assert "def refund_pending_bridge_lock" in db
    rocks = Path("storage/rocks_store.py").read_text(encoding="utf-8")
    assert "def debit_and_create_bridge_lock" in rocks
    assert "def refund_pending_bridge_lock" in rocks


def test_config_require_l1_event():
    cfg = Path("runtime/config.py").read_text(encoding="utf-8")
    assert "bridge_require_l1_event" in cfg
    assert "BRIDGE_REQUIRE_L1_EVENT" in cfg
    assert "BRIDGE_REQUIRE_L1_EVENT=true requires a real BRIDGE_L1_LOCK_CONTRACT" in cfg
