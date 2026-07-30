# tests/unit/test_prometheus_export_format.py — ADR 0015 MetricsExporterPort
"""Validate Prometheus text grammar and required abs_* series via MetricsExporterPort."""

from __future__ import annotations

import math
import re

from observability.metrics import MetricsCollector
from observability.ports import (
    MetricsSnapshot,
    NullMetricsExporter,
    PrometheusMetricsExporter,
    compute_tps_from_chain_metrics,
    p2p_security_ok_from_status,
)

_METRIC_LINE = re.compile(
    r"^(?:# (?:HELP|TYPE) .+|[a-zA-Z_:][a-zA-Z0-9_:]*(?:\{[^}]*\})? [-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?\d+)?)$"
)


def test_compute_tps_from_window_metrics():
    assert compute_tps_from_chain_metrics({"window_tx_count": 100, "window_elapsed_sec": 10}) == 10.0
    assert compute_tps_from_chain_metrics({"tps": 3.5}) == 3.5
    assert compute_tps_from_chain_metrics(None) == 0.0
    assert compute_tps_from_chain_metrics({"tps": float("nan")}) == 0.0


def test_p2p_security_ok_predicate():
    assert p2p_security_ok_from_status({}) is False
    assert p2p_security_ok_from_status({"active_bans": 0}) is True
    assert p2p_security_ok_from_status({"security_ok": False}) is False


def test_null_exporter_minimal_valid():
    text = NullMetricsExporter().render(MetricsSnapshot(node_id="n1"))
    assert "abs_metrics_exporter_null" in text
    assert 'node_id="n1"' in text


def test_prometheus_exporter_required_series_and_grammar():
    mc = MetricsCollector()
    exporter = PrometheusMetricsExporter(mc)
    snap = MetricsSnapshot(
        node_id="n1",
        height=42,
        peers=3,
        mempool=7,
        validators=4,
        tps=1.25,
        p2p_security_ok=True,
        p2p_security={
            "handshake_rejects": 2,
            "shape_rejects_total": 5,
            "active_bans": 1,
            "rate_limit_drops": 7,
            "rate_limit_per_sec": 50,
            "shape_rejects": {"bad_wire_tx": 3},
            "ops_errors": {"peer_send_fail": 1},
        },
        native_crypto={"available": True, "required": False, "self_test": True, "kernels": []},
        bridge_health={"enabled": False, "mode": "off", "required": False, "ok": False},
    )
    text = exporter.render(snap)
    assert "# HELP abs_peers_connected" in text
    assert "# TYPE abs_chain_height gauge" in text
    assert 'abs_peers_connected{node_id="n1"} 3' in text
    assert 'abs_chain_height{node_id="n1"} 42' in text
    assert 'abs_tps{node_id="n1"} 1.250000' in text
    assert 'abs_p2p_security_ok{node_id="n1"} 1' in text
    assert "abs_p2p_handshake_rejects_total" in text
    assert "abs_p2p_shape_rejects_total" in text

    for line in text.strip().splitlines():
        assert _METRIC_LINE.match(line), f"invalid prometheus line: {line!r}"
        if line.startswith("#"):
            continue
        value = line.rsplit(" ", 1)[-1]
        fval = float(value)
        assert not math.isnan(fval)
        assert not math.isinf(fval)


def test_prometheus_exporter_deterministic_for_same_snapshot():
    exporter = PrometheusMetricsExporter(MetricsCollector())
    snap = MetricsSnapshot(node_id="x", height=1, peers=0, tps=0.0, p2p_security_ok=False)
    a = exporter.render(snap)
    b = exporter.render(snap)
    # Uptime may drift; strip uptime lines for equality of structural series.
    def _strip_uptime(t: str) -> str:
        return "\n".join(
            ln for ln in t.splitlines() if "abs_uptime_seconds" not in ln
        )

    assert _strip_uptime(a) == _strip_uptime(b)
