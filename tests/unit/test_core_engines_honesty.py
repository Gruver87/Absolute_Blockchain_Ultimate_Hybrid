#!/usr/bin/env python3
"""v1.3.24 honesty: core engines prod, status wire probe, IMS canonical, Rocks meta/tx."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_prod_requires_core_engines():
    main_py = Path("main.py").read_text(encoding="utf-8")
    assert "Production mode requires StateEngine" in main_py
    assert "Production mode requires FinalityEngine" in main_py
    assert "Production mode requires ImmutableStateManager" in main_py


def test_status_degrades_on_wire_probe():
    http_py = Path("api/http.py").read_text(encoding="utf-8")
    assert "peer_count > 0 and not wire_probe_probed" in http_py
    assert "wire_probe_probed and not wire_probe_ok" in http_py


def test_ready_prod_checks_core_engines():
    http_py = Path("api/http.py").read_text(encoding="utf-8")
    assert 'checks["state_engine"]' in http_py
    assert 'checks["finality_engine"]' in http_py
    assert 'checks["immutable_state"]' in http_py


def test_ims_absent_not_canonical():
    http_py = Path("api/http.py").read_text(encoding="utf-8")
    assert '"ims_available": False' in http_py
    assert "DB-only is never IMS-canonical" in http_py


def test_metrics_core_engine_gauges():
    from observability.metrics import MetricsCollector

    text = MetricsCollector().render_prometheus(
        node_id="n1",
        core_engines={
            "state_engine": True,
            "finality_engine": False,
            "immutable_state": True,
        },
    )
    assert 'abs_state_engine_available{node_id="n1"} 1' in text
    assert 'abs_finality_engine_available{node_id="n1"} 0' in text
    assert 'abs_ims_available{node_id="n1"} 1' in text


def test_rocks_meta_and_tx_list_bump_decode():
    rocks = Path("storage/rocks_store.py").read_text(encoding="utf-8")
    assert rocks.count("self._json_decode_failures += 1") >= 15
    assert "corrupt meta" in rocks
    assert "corrupt address_tx row skipped" in rocks
    assert "corrupt recent_tx row skipped" in rocks
    assert "corrupt block_tx row skipped" in rocks
