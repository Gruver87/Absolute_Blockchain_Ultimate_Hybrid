"""verify_p2p_ci fail-closed skip policy."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "verify_p2p_ci.py"


def _load_verify():
    spec = importlib.util.spec_from_file_location("verify_p2p_ci", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_skip_or_fail_without_env(monkeypatch):
    mod = _load_verify()
    monkeypatch.delenv("VERIFY_P2P_ALLOW_SKIP", raising=False)
    assert mod._verify_p2p_skip_or_fail("native wheel missing") == 1


def test_skip_or_fail_with_env(monkeypatch):
    mod = _load_verify()
    monkeypatch.setenv("VERIFY_P2P_ALLOW_SKIP", "1")
    assert mod._verify_p2p_skip_or_fail("native wheel missing") == 0


def test_adversarial_wave_skip_fail_closed(monkeypatch):
    mod = _load_verify()
    monkeypatch.delenv("VERIFY_P2P_ALLOW_SKIP", raising=False)
    assert mod.verify_adversarial("http://127.0.0.1:8080", {"api_wave": 40, "deployment_mode": "dev"}) == 1


def test_adversarial_prod_skip_fail_closed(monkeypatch):
    mod = _load_verify()
    monkeypatch.delenv("VERIFY_P2P_ALLOW_SKIP", raising=False)
    rc = mod.verify_adversarial(
        "http://127.0.0.1:8080",
        {"api_wave": 61, "deployment_mode": "prod"},
    )
    assert rc == 1
