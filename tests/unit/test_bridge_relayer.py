#!/usr/bin/env python3
"""Bridge relayer worker tests."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from bridge.oracle_auth import sign_payload, verify_signature


def test_oracle_hmac_roundtrip():
    secret = "test-secret"
    body = json.dumps({"tx_hash": "0xabc"}).encode()
    sig = sign_payload(secret, body)
    assert verify_signature(secret, body, sig)
    assert not verify_signature(secret, body, "bad")


def test_relayer_module_imports():
    import importlib.util
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "scripts",
        "bridge_relayer.py",
    )
    spec = importlib.util.spec_from_file_location("bridge_relayer", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "process_pending")
    assert hasattr(mod, "process_l1_queue")
    assert hasattr(mod, "_oracle_post")


def test_relayer_l1_queue_dry_run(tmp_path, monkeypatch):
    import importlib.util
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "scripts",
        "bridge_relayer.py",
    )
    spec = importlib.util.spec_from_file_location("bridge_relayer", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    queue_path = str(tmp_path / "q.json")
    with open(queue_path, "w", encoding="utf-8") as f:
        json.dump({"outbound": [], "incoming": []}, f)

    monkeypatch.setattr(mod, "process_pending", lambda *a, **k: 0)
    n = mod.process_l1_queue("http://127.0.0.1:8080", "secret", queue_path, dry_run=True)
    assert n == 0
