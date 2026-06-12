#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prometheus-совместимые метрики узла."""

import time
from typing import Any, Optional


class MetricsCollector:
    """Сбор метрик для GET /metrics (text/plain Prometheus format)."""

    def __init__(self):
        self.start_time = time.time()
        self.rpc_requests = 0
        self.http_requests = 0
        self.errors = 0

    def uptime_seconds(self) -> float:
        return time.time() - self.start_time

    def inc_http(self) -> None:
        self.http_requests += 1

    def inc_rpc(self) -> None:
        self.rpc_requests += 1

    def inc_error(self) -> None:
        self.errors += 1

    def render_prometheus(
        self,
        *,
        height: int = 0,
        peers: int = 0,
        mempool: int = 0,
        validators: int = 0,
        deployment_mode: str = "dev",
        node_id: str = "node-1",
    ) -> str:
        lines = [
            "# HELP abs_uptime_seconds Node uptime",
            "# TYPE abs_uptime_seconds gauge",
            f"abs_uptime_seconds{{node_id=\"{node_id}\"}} {self.uptime_seconds():.2f}",
            "# HELP abs_chain_height Current block height",
            "# TYPE abs_chain_height gauge",
            f"abs_chain_height{{node_id=\"{node_id}\"}} {height}",
            "# HELP abs_peers_connected Connected P2P peers",
            "# TYPE abs_peers_connected gauge",
            f"abs_peers_connected{{node_id=\"{node_id}\"}} {peers}",
            "# HELP abs_mempool_size Pending transactions",
            "# TYPE abs_mempool_size gauge",
            f"abs_mempool_size{{node_id=\"{node_id}\"}} {mempool}",
            "# HELP abs_validators_active Active validators",
            "# TYPE abs_validators_active gauge",
            f"abs_validators_active{{node_id=\"{node_id}\"}} {validators}",
            "# HELP abs_http_requests_total HTTP requests served",
            "# TYPE abs_http_requests_total counter",
            f"abs_http_requests_total{{node_id=\"{node_id}\"}} {self.http_requests}",
            "# HELP abs_errors_total API errors",
            "# TYPE abs_errors_total counter",
            f"abs_errors_total{{node_id=\"{node_id}\"}} {self.errors}",
            f"abs_deployment_mode{{node_id=\"{node_id}\",mode=\"{deployment_mode}\"}} 1",
        ]
        return "\n".join(lines) + "\n"
