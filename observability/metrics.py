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
        native_crypto: Optional[dict[str, Any]] = None,
        bridge_health: Optional[dict[str, Any]] = None,
    ) -> str:
        native_crypto = native_crypto or {}
        bridge_health = bridge_health or {}
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
            "# HELP abs_native_crypto_available Native Rust/PyO3 crypto module availability",
            "# TYPE abs_native_crypto_available gauge",
            (
                f"abs_native_crypto_available{{node_id=\"{node_id}\"}} "
                f"{1 if native_crypto.get('available') else 0}"
            ),
            "# HELP abs_native_crypto_required Whether this node requires native crypto",
            "# TYPE abs_native_crypto_required gauge",
            (
                f"abs_native_crypto_required{{node_id=\"{node_id}\"}} "
                f"{1 if native_crypto.get('required') else 0}"
            ),
            "# HELP abs_native_crypto_self_test Native crypto self-test status",
            "# TYPE abs_native_crypto_self_test gauge",
            (
                f"abs_native_crypto_self_test{{node_id=\"{node_id}\"}} "
                f"{1 if native_crypto.get('self_test') else 0}"
            ),
            "# HELP abs_rust_bridge_enabled Whether the Rust bridge path is enabled",
            "# TYPE abs_rust_bridge_enabled gauge",
            (
                f"abs_rust_bridge_enabled{{node_id=\"{node_id}\"}} "
                f"{1 if bridge_health.get('enabled') and bridge_health.get('mode') == 'rust' else 0}"
            ),
            "# HELP abs_rust_bridge_required Whether readiness requires the Rust bridge",
            "# TYPE abs_rust_bridge_required gauge",
            (
                f"abs_rust_bridge_required{{node_id=\"{node_id}\"}} "
                f"{1 if bridge_health.get('required') else 0}"
            ),
            "# HELP abs_rust_bridge_ok Rust bridge JSON smoke-test status",
            "# TYPE abs_rust_bridge_ok gauge",
            (
                f"abs_rust_bridge_ok{{node_id=\"{node_id}\"}} "
                f"{1 if bridge_health.get('ok') else 0}"
            ),
            "# HELP abs_l1_rpc_configured Whether any L1 RPC URL is configured",
            "# TYPE abs_l1_rpc_configured gauge",
            (
                f"abs_l1_rpc_configured{{node_id=\"{node_id}\"}} "
                f"{1 if (bridge_health.get('l1_rpc') or {}).get('configured') else 0}"
            ),
            "# HELP abs_l1_rpc_required Whether readiness requires live L1 RPC",
            "# TYPE abs_l1_rpc_required gauge",
            (
                f"abs_l1_rpc_required{{node_id=\"{node_id}\"}} "
                f"{1 if (bridge_health.get('l1_rpc') or {}).get('required') else 0}"
            ),
            "# HELP abs_l1_rpc_ok L1 RPC reachability probe status",
            "# TYPE abs_l1_rpc_ok gauge",
            (
                f"abs_l1_rpc_ok{{node_id=\"{node_id}\"}} "
                f"{1 if (bridge_health.get('l1_rpc') or {}).get('ok') else 0}"
            ),
        ]
        for kernel in native_crypto.get("kernels", []):
            safe_kernel = str(kernel).replace("\\", "\\\\").replace('"', '\\"')
            lines.append(
                f"abs_native_crypto_kernel_enabled{{node_id=\"{node_id}\",kernel=\"{safe_kernel}\"}} 1"
            )
        return "\n".join(lines) + "\n"
