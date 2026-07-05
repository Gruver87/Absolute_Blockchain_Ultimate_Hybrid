#!/usr/bin/env python3
"""Bridge relayer core — prod L1-proof fail-closed and preflight."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from bridge import relayer


def test_relayer_skips_blind_pending_when_l1_proof_required(monkeypatch):
    monkeypatch.setenv("BRIDGE_REQUIRE_L1_PROOF", "true")
    calls = []

    def fake_get(url, timeout=10.0):
        calls.append(url)
        return {"locks": [{"tx_hash": "0xabc", "status": "pending", "amount": 1, "to_chain": "eth"}]}

    monkeypatch.setattr(relayer, "http_get_json", fake_get)
    monkeypatch.setattr(relayer, "oracle_post", lambda *a, **k: {"confirmed": True})

    n = relayer.process_pending("http://127.0.0.1:8080", "secret")
    assert n == 0
    assert calls == []


def test_relayer_confirms_pending_in_dev(monkeypatch):
    monkeypatch.delenv("BRIDGE_REQUIRE_L1_PROOF", raising=False)
    posts = []

    monkeypatch.setattr(
        relayer,
        "http_get_json",
        lambda url, timeout=10.0: {"locks": [{"tx_hash": "0xabc", "status": "pending"}]},
    )
    monkeypatch.setattr(
        relayer,
        "oracle_post",
        lambda base, path, payload, secret: posts.append((path, payload)) or {"confirmed": True},
    )

    n = relayer.process_pending("http://127.0.0.1:8080", "secret")
    assert n == 1
    assert posts[0][0].endswith("/oracle/confirm-lock")


def test_relayer_preflight_requires_secret():
    out = relayer.check_relayer_readiness("http://127.0.0.1:8080", "")
    assert out["ok"] is False
    assert any("ORACLE" in e for e in out["errors"])


def test_relayer_preflight_node_unreachable(monkeypatch):
    def _fail(*args, **kwargs):
        raise OSError("down")

    monkeypatch.setattr(relayer, "http_get_json", _fail)
    out = relayer.check_relayer_readiness("http://127.0.0.1:8080", "x" * 32, probe_l1=False)
    assert out["ok"] is False
    assert any("unreachable" in e for e in out["errors"])


def test_relayer_l1_queue_http_mode(monkeypatch):
    monkeypatch.setenv("BRIDGE_L1_QUEUE_HTTP", "true")
    posts = []

    monkeypatch.setattr(
        relayer,
        "http_get_json",
        lambda url, timeout=10.0: {
            "queue": {
                "outbound": [],
                "incoming": [{
                    "l1_tx_hash": "0x1",
                    "recipient": "0xr",
                    "amount": 1,
                    "from_chain": "ethereum",
                    "rpc_url": "http://rpc",
                }],
            }
        },
    )
    monkeypatch.setattr(relayer, "is_tx_confirmed", lambda *a, **k: True)
    monkeypatch.setattr(
        relayer,
        "oracle_post",
        lambda base, path, payload, secret: posts.append((path, payload)) or {"confirmed": True},
    )

    n = relayer.process_l1_queue("http://127.0.0.1:8080", "secret", "ignored.json")
    assert n == 1
    assert any(p[0].endswith("/l1-queue-sync") for p in posts)


def test_relayer_preflight_ok(monkeypatch):
    monkeypatch.setattr(
        relayer,
        "http_get_json",
        lambda url, timeout=10.0: {
            "deployment_mode": "prod",
            "bridge_enabled": True,
            "bridge_mode": "rust",
            "bridge_oracle_enabled": True,
            "height": 10,
        },
    )
    monkeypatch.setattr(
        "bridge.health.check_l1_rpc_health",
        lambda cfg, timeout=3.0: {"required": True, "configured": True, "ok": True},
    )
    monkeypatch.setattr(relayer, "relayer_require_l1_proof", lambda: False)
    out = relayer.check_relayer_readiness("http://127.0.0.1:8080", "x" * 32)
    assert out["ok"] is True
    assert out["require_l1_proof"] is False
