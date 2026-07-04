#!/usr/bin/env python3
"""prod_smoke.py unit tests."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import prod_smoke


def _ready_payload():
    return {
        "status": "ready",
        "rust_bridge": {"required": False, "ok": True},
        "l1_rpc": {"required": False, "ok": True},
    }


def _status_payload(*, bridge_enabled: bool = True):
    return {
        "deployment_mode": "prod",
        "bridge_enabled": bridge_enabled,
        "require_native_crypto": True,
        "chain_id": 778888,
        "state_root_strict_p2p": True,
        "consensus": {"mode": "unified", "attestation_count": 1},
        "genesis_ceremony": {
            "ready": True,
            "mainnet_addresses_ready": True,
            "ceremony_hash": "abc123",
            "errors": [],
        },
    }


def _fake_fetch_factory(handlers):
    """Match more specific path suffixes before generic /status."""
    def fake_fetch(url, timeout=8.0):
        for suffix, handler in handlers:
            if url.endswith(suffix):
                return handler()
        raise AssertionError(url)
    return fake_fetch


def test_prod_smoke_ok(monkeypatch):
    monkeypatch.delenv("GENESIS_CEREMONY_HASH", raising=False)
    handlers = [
        ("/bridge/relayer/status", lambda: (
            200,
            {
                "oracle_hmac_configured": True,
                "require_l1_proof": True,
                "blind_pending_confirm_allowed": False,
            },
        )),
        ("/chain/consistency/harness", lambda: (
            200,
            {
                "harness_healthy": True,
                "canonical_state_root_source": "blockchain.database",
            },
        )),
        ("/health/ready", lambda: (200, _ready_payload())),
        ("/features", lambda: (
            200,
            {
                "wasm": {"enabled": False, "tier": "r-and-d", "prod_blocked_reason": "blocked"},
            },
        )),
        ("/bridge", lambda: (
            200,
            {"mode": "rust", "l1_rpc": {"required": True, "ok": True}},
        )),
        ("/status", lambda: (200, _status_payload())),
    ]

    with patch.object(prod_smoke, "_fetch", _fake_fetch_factory(handlers)):
        with patch("urllib.request.urlopen") as open_mock:
            open_mock.return_value.__enter__ = lambda s: s
            open_mock.return_value.__exit__ = MagicMock(return_value=False)
            open_mock.return_value.status = 200
            open_mock.return_value.read.return_value = (
                b"abs_native_crypto_self_test 1\nabs_rust_bridge_ok 1\nabs_l1_rpc_ok 1\n"
            )
            report = prod_smoke.run_prod_smoke("http://127.0.0.1:8080")

    assert report["ok"] is True
    assert report["errors"] == []


def test_prod_smoke_bridge_disabled_skips_bridge_checks(monkeypatch):
    monkeypatch.delenv("GENESIS_CEREMONY_HASH", raising=False)
    handlers = [
        ("/chain/consistency/harness", lambda: (
            200,
            {
                "harness_healthy": True,
                "canonical_state_root_source": "blockchain.database",
            },
        )),
        ("/health/ready", lambda: (200, _ready_payload())),
        ("/features", lambda: (
            200,
            {
                "wasm": {"enabled": False, "tier": "r-and-d", "prod_blocked_reason": "blocked"},
            },
        )),
        ("/status", lambda: (200, _status_payload(bridge_enabled=False))),
    ]

    with patch.object(prod_smoke, "_fetch", _fake_fetch_factory(handlers)):
        with patch("urllib.request.urlopen") as open_mock:
            open_mock.return_value.__enter__ = lambda s: s
            open_mock.return_value.__exit__ = MagicMock(return_value=False)
            open_mock.return_value.status = 200
            open_mock.return_value.read.return_value = b"abs_native_crypto_self_test 1\n"
            report = prod_smoke.run_prod_smoke("http://127.0.0.1:8080")

    assert report["ok"] is True
    assert report["checks"].get("bridge_disabled") is True


def test_prod_smoke_fails_when_not_ready(monkeypatch):
    monkeypatch.delenv("GENESIS_CEREMONY_HASH", raising=False)
    def _not_ready_status():
        payload = _status_payload()
        payload["bridge_enabled"] = False
        return 200, payload

    handlers = [
        ("/chain/consistency/harness", lambda: (
            200,
            {
                "harness_healthy": True,
                "canonical_state_root_source": "blockchain.database",
            },
        )),
        ("/health/ready", lambda: (503, {"status": "not_ready"})),
        ("/features", lambda: (
            200,
            {"wasm": {"enabled": False, "tier": "r-and-d", "prod_blocked_reason": "x"}},
        )),
        ("/status", _not_ready_status),
    ]

    with patch.object(prod_smoke, "_fetch", _fake_fetch_factory(handlers)):
        report = prod_smoke.run_prod_smoke("http://127.0.0.1:8080")
    assert report["ok"] is False
    assert any("health/ready" in e for e in report["errors"])
