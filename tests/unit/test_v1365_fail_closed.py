#!/usr/bin/env python3
"""v1.3.65: L1 security / fail-closed hardening."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_verify_attestation_binds_validator_identity():
    from crypto.validator_keys import ValidatorKeys
    from crypto.wallet import Wallet

    keys = ValidatorKeys().initialize(Wallet.create_new())
    att = keys.sign_attestation({"hash": "ab" * 32, "number": 1}, slot=1)
    assert keys.verify_attestation(att) is True
    att["validator"] = "0x" + "11" * 20
    assert keys.verify_attestation(att) is False


def test_amount_native_required_reads_abs_env(monkeypatch):
    from runtime import amount

    monkeypatch.delenv("REQUIRE_NATIVE_CRYPTO", raising=False)
    monkeypatch.setenv("ABS_REQUIRE_NATIVE_CRYPTO", "true")
    assert amount._native_required() is True
    monkeypatch.delenv("ABS_REQUIRE_NATIVE_CRYPTO", raising=False)
    monkeypatch.setenv("REQUIRE_NATIVE_CRYPTO", "1")
    assert amount._native_required() is True


def test_native_apply_fail_closed_helper():
    from core.blockchain import Blockchain
    from runtime.config import Config

    cfg = Config()
    cfg.require_native_crypto = True
    bc = Blockchain.__new__(Blockchain)
    bc.config = cfg
    assert bc._native_apply_fail_closed() is True
    cfg.require_native_crypto = False
    cfg.deployment_mode = "prod"
    assert bc._native_apply_fail_closed() is True
    cfg.deployment_mode = "dev"
    assert bc._native_apply_fail_closed() is False


def test_corrupt_account_raises(tmp_path):
    try:
        import abs_native  # type: ignore

        if not hasattr(abs_native, "RocksEngine"):
            pytest.skip("no RocksEngine")
    except Exception:
        pytest.skip("no abs_native")

    from storage.rocks_store import AccountCorruptError, RocksChainStore
    from storage import keycodec as kc

    store = RocksChainStore(str(tmp_path / "c65"), synchronous="FULL")
    store.initialize()
    try:
        store._engine.put(kc.key_account("0xaaa"), b"{not-json")
        with pytest.raises(AccountCorruptError):
            store._load_account("0xaaa")
    finally:
        store.close()


def test_http_body_helpers_and_needles():
    from api import http as http_mod

    assert http_mod._http_max_body_bytes(None) == 1_048_576
    cfg = MagicMock()
    cfg.http_max_body_bytes = 100
    cfg.jsonrpc_max_batch = 5
    assert http_mod._http_max_body_bytes(cfg) == 100
    assert http_mod._jsonrpc_max_batch(cfg) == 5
    text = (ROOT / "api" / "http.py").read_text(encoding="utf-8")
    assert "_read_limited_body" in text
    assert "batch too large" in text
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "validator_register_disabled" in p2p
    assert "attestation_verifier_unavailable" in p2p
    vk = (ROOT / "crypto" / "validator_keys.py").read_text(encoding="utf-8")
    assert "derive_address" in vk
