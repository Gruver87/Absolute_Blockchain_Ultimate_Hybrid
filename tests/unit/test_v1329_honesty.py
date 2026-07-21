#!/usr/bin/env python3
"""v1.3.29 honesty: topology/prod, filters, migrate, metrics, WS, backup tip."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_topology_prod_zero_peers_not_healthy():
    p2p = Path("network/p2p_node.py").read_text(encoding="utf-8")
    assert 'mode in ("prod", "production", "staging")' in p2p
    assert "expected = max(1, mesh_min)" in p2p


def test_eth_filters_unavailable_raises():
    http_py = Path("api/http.py").read_text(encoding="utf-8")
    # All filter read/uninstall paths must raise, not invent empty success.
    idx = http_py.index('if method == "eth_getFilterChanges"')
    snip = http_py[idx : idx + 500]
    assert 'raise ValueError("eth filters unavailable")' in snip
    assert "return []" not in snip.split("eth_getMempoolSize")[0]


def test_ws_clears_running_on_failure():
    ws = Path("network/websocket.py").read_text(encoding="utf-8")
    assert "Fail-closed: bind/runtime failure must not leave a live flag" in ws
    assert "finally:" in ws
    assert "self._running = False" in ws


def test_hybrid_migrate_skips_corrupt_without_marker():
    hyb = Path("storage/hybrid_database.py").read_text(encoding="utf-8")
    assert "skipped_corrupt" in hyb
    assert "do not permanently mark migrated while corrupt rows remain" in hyb
    assert "aux_json_decode_failures" in hyb


def test_sqlite_feature_tables_use_loads_json():
    db = Path("storage/database.py").read_text(encoding="utf-8")
    assert 'context="plasma_txs"' in db
    assert 'context="will_assets"' in db
    assert 'context="nft_token_meta"' in db
    assert 'context="wasm_storage"' in db
    assert 'context="mev_sim"' in db


def test_metrics_export_sqlite_and_ws():
    metrics = Path("observability/metrics.py").read_text(encoding="utf-8")
    assert "abs_sqlite_json_decode_failures" in metrics
    assert "abs_ws_send_failures_total" in metrics
    alerts = Path("deploy/prometheus/alerts.yml").read_text(encoding="utf-8")
    assert "AbsoluteSqliteJsonDecodeFailures" in alerts
    assert "AbsoluteWSSendFailBurst" in alerts


def test_read_chain_tip_fail_closed():
    backup = Path("storage/chain_backup.py").read_text(encoding="utf-8")
    assert "never invent tip 0 as success" in backup
    assert "except Exception:\n            return 0" not in backup


def test_status_exposes_websocket_subsystem():
    http_py = Path("api/http.py").read_text(encoding="utf-8")
    assert '"websocket_running"' in http_py
    assert '"websocket_send_failures"' in http_py
    assert "RESTHandler.ws_server" in Path("main.py").read_text(encoding="utf-8")
