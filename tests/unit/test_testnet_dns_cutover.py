#!/usr/bin/env python3
"""Public testnet DNS cutover probe tests."""

import importlib.util
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def _load():
    path = ROOT / "scripts" / "testnet_dns_cutover.py"
    spec = importlib.util.spec_from_file_location("testnet_dns_cutover", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_dns_cutover_module_exists():
    assert (ROOT / "scripts" / "testnet_dns_cutover.py").is_file()
    assert (ROOT / "scripts" / "prepare_testnet_dns_cutover.ps1").is_file()
    assert (ROOT / "scripts" / "vps_testnet_bootstrap_mesh3.sh").is_file()


def test_normalize_domain_strips_scheme():
    mod = _load()
    assert mod._normalize_domain("https://testnet.example.com/api") == "testnet.example.com"


def test_api_base_uses_https_prefix():
    mod = _load()
    assert mod._api_base("testnet.example.com", "/api") == "https://testnet.example.com/api"


def test_invalid_domain_fails_fast():
    mod = _load()
    errors, _warnings, meta = mod.run_testnet_dns_cutover(domain="localhost", resolve_dns=False, check_tls=False)
    assert errors
    assert meta["ready"] is False


def test_https_probe_ok_with_mocks():
    mod = _load()
    ready = {"status": "ready"}
    status = {"chain_id": 77777, "height": 12, "peers": 2}
    harness = {"harness_healthy": True, "tip_state_aligned": True}

    def fake_get(url, timeout=12.0):
        if "/health/ready" in url:
            return ready
        if "/status" in url:
            return status
        return harness

    with patch.object(mod, "_resolve_dns", return_value=(["203.0.113.10"], None)), patch.object(
        mod, "_tls_summary", return_value=({"not_after": "Jan  1 00:00:00 2027 GMT", "issuer_cn": "R3"}, None)
    ), patch.object(mod, "_get_json", side_effect=fake_get):
        errors, warnings, meta = mod.run_testnet_dns_cutover(domain="testnet.example.com")
    assert errors == []
    assert meta["ready"] is True
    assert meta["dns_addresses"] == ["203.0.113.10"]
    assert any("cert expires" in w for w in warnings)
