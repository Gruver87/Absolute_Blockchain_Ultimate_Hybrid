#!/usr/bin/env python3
"""v1.3.53: apply isolation metrics + dedicated sync executor."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from observability.metrics import MetricsCollector


def test_metrics_emit_apply_isolation():
    text = MetricsCollector().render_prometheus(
        node_id="n1",
        apply_isolation={
            "queue_depth": 3,
            "wait_seconds_total": 1.5,
            "reject_total": 7,
            "import_offload_total": 42,
        },
    )
    assert "abs_chain_apply_queue_depth" in text
    assert 'abs_chain_apply_queue_depth{node_id="n1"} 3' in text
    assert "abs_chain_apply_wait_seconds_total" in text
    assert "abs_chain_apply_reject_total" in text
    assert 'abs_chain_apply_reject_total{node_id="n1"} 7' in text
    assert "abs_p2p_import_offload_total" in text
    assert 'abs_p2p_import_offload_total{node_id="n1"} 42' in text


def test_wiring():
    main = Path("main.py").read_text(encoding="utf-8")
    assert "ThreadPoolExecutor" in main
    assert "sync_executor" in main
    assert "apply queue backpressure" in main
    p2p = Path("network/p2p_node.py").read_text(encoding="utf-8")
    assert "_sync_state_async" in p2p
    assert "sync_executor" in p2p
    assert "run_in_executor(None, self.sync_engine.sync_state)" not in p2p
    metrics = Path("observability/metrics.py").read_text(encoding="utf-8")
    assert "abs_chain_apply_queue_depth" in metrics
    http = Path("api/http.py").read_text(encoding="utf-8")
    assert "_apply_isolation_metrics" in http
    assert "apply_isolation=" in http
