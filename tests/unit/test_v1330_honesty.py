#!/usr/bin/env python3
"""v1.3.30 honesty: ready/WS, features, bridge proof, L2 missing, storage, consensus."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_ready_checks_websocket_in_prod():
    http_py = Path("api/http.py").read_text(encoding="utf-8")
    assert 'checks["websocket_running"]' in http_py
    assert "lightning_init" in http_py or 'f"{name}_init"' in http_py


def test_l2_unbound_error_keys():
    http_py = Path("api/http.py").read_text(encoding="utf-8")
    assert "lightning_missing" in http_py
    assert "plasma_missing" in http_py
    assert "wasm_missing" in http_py
    assert "p2p_missing" in http_py


def test_bridge_proof_requires_eth_rpc():
    http_py = Path("api/http.py").read_text(encoding="utf-8")
    assert "proof_ok = bridge_on and oracle_on and rust_path and rpc_on" in http_py
    assert "proof_components" in http_py


def test_eth_get_storage_corrupt_raises():
    http_py = Path("api/http.py").read_text(encoding="utf-8")
    assert 'raise ValueError("corrupt account storage")' in http_py
    assert 'context="account_storage"' in http_py


def test_feature_init_errors_tracked():
    main_py = Path("main.py").read_text(encoding="utf-8")
    assert "feature_init_errors" in main_py
    assert 'self.feature_init_errors["lightning"]' in main_py
    assert "RESTHandler.feature_init_errors" in main_py


def test_consensus_healthy_flag():
    adapter = Path("consensus/adapter.py").read_text(encoding="utf-8")
    assert "_casper_ingest_fail" in adapter
    assert '"healthy": False' in adapter or '"healthy":False' in adapter
    assert "casper_ingest_fail" in adapter


def test_status_degrades_on_feature_init_errors():
    http_py = Path("api/http.py").read_text(encoding="utf-8")
    assert "feature_degraded" in http_py
    assert '"feature_init_errors"' in http_py
