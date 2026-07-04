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
        "rust_bridge": {"required": True, "ok": True},
        "l1_rpc": {"required": True, "ok": True},
    }


def test_prod_smoke_ok():
    def fake_fetch(url, timeout=8.0):
        if url.endswith("/health/ready"):
            return 200, _ready_payload()
        if url.endswith("/bridge"):
            return 200, {"mode": "rust", "l1_rpc": {"required": True, "ok": True}}
        if url.endswith("/bridge/relayer/status"):
            return 200, {
                "oracle_hmac_configured": True,
                "require_l1_proof": True,
                "blind_pending_confirm_allowed": False,
            }
        raise AssertionError(url)

    with patch.object(prod_smoke, "_fetch", fake_fetch):
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


def test_prod_smoke_fails_when_not_ready():
    with patch.object(prod_smoke, "_fetch", lambda url, timeout=8.0: (503, {"status": "not_ready"})):
        report = prod_smoke.run_prod_smoke("http://127.0.0.1:8080")
    assert report["ok"] is False
    assert any("health/ready" in e for e in report["errors"])
