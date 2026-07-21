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
        p2p_security: Optional[dict[str, Any]] = None,
        rocksdb_tuning: Optional[dict[str, Any]] = None,
        sync_status: Optional[dict[str, Any]] = None,
        core_engines: Optional[dict[str, Any]] = None,
        ws_stats: Optional[dict[str, Any]] = None,
    ) -> str:
        native_crypto = native_crypto or {}
        bridge_health = bridge_health or {}
        p2p_security = p2p_security or {}
        rocksdb_tuning = rocksdb_tuning or {}
        sync_status = sync_status or {}
        core_engines = core_engines or {}
        ws_stats = ws_stats or {}
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
            "# HELP abs_l1_rpc_probed Whether a live L1 eth_blockNumber probe ran",
            "# TYPE abs_l1_rpc_probed gauge",
            (
                f"abs_l1_rpc_probed{{node_id=\"{node_id}\"}} "
                f"{1 if (bridge_health.get('l1_rpc') or {}).get('probed') else 0}"
            ),
            "# HELP abs_p2p_handshake_rejects_total Handshake rejects (payload + mid-session)",
            "# TYPE abs_p2p_handshake_rejects_total counter",
            (
                f"abs_p2p_handshake_rejects_total{{node_id=\"{node_id}\"}} "
                f"{int(p2p_security.get('handshake_rejects', 0) or 0)}"
            ),
            "# HELP abs_p2p_attestation_local_fail_total Local attestation sign failures",
            "# TYPE abs_p2p_attestation_local_fail_total counter",
            (
                f"abs_p2p_attestation_local_fail_total{{node_id=\"{node_id}\"}} "
                f"{int(p2p_security.get('attestation_local_fail', 0) or 0)}"
            ),
            "# HELP abs_p2p_peer_tx_reject_total Semantic peer tx rejects / mempool drops",
            "# TYPE abs_p2p_peer_tx_reject_total counter",
            (
                f"abs_p2p_peer_tx_reject_total{{node_id=\"{node_id}\"}} "
                f"{int((p2p_security.get('ops_errors') or {}).get('peer_tx_reject', 0) or 0)}"
            ),
            "# HELP abs_p2p_shape_rejects_total Fail-closed P2P shape rejects",
            "# TYPE abs_p2p_shape_rejects_total counter",
            (
                f"abs_p2p_shape_rejects_total{{node_id=\"{node_id}\"}} "
                f"{int(p2p_security.get('shape_rejects_total', 0) or 0)}"
            ),
            "# HELP abs_p2p_active_bans Currently banned peer keys",
            "# TYPE abs_p2p_active_bans gauge",
            (
                f"abs_p2p_active_bans{{node_id=\"{node_id}\"}} "
                f"{int(p2p_security.get('active_bans', 0) or 0)}"
            ),
            "# HELP abs_p2p_rate_limit_drops_total P2P per-peer rate-limit drops (strikes)",
            "# TYPE abs_p2p_rate_limit_drops_total counter",
            (
                f"abs_p2p_rate_limit_drops_total{{node_id=\"{node_id}\"}} "
                f"{int(p2p_security.get('rate_limit_drops', 0) or 0)}"
            ),
            "# HELP abs_p2p_shape_rejects Fail-closed P2P shape rejects by reason",
            "# TYPE abs_p2p_shape_rejects counter",
        ]
        for reason, count in (p2p_security.get("shape_rejects") or {}).items():
            safe_reason = (
                str(reason)
                .replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("\n", " ")
            )
            lines.append(
                f"abs_p2p_shape_rejects{{node_id=\"{node_id}\",reason=\"{safe_reason}\"}} "
                f"{int(count or 0)}"
            )
        ops_errors = dict(p2p_security.get("ops_errors") or {})
        lines.extend(
            [
                "# HELP abs_p2p_peer_send_fail_total Outbound P2P send failures",
                "# TYPE abs_p2p_peer_send_fail_total counter",
                (
                    f"abs_p2p_peer_send_fail_total{{node_id=\"{node_id}\"}} "
                    f"{int(ops_errors.get('peer_send_fail', 0) or 0)}"
                ),
                "# HELP abs_p2p_ops_errors P2P operational error counters by kind",
                "# TYPE abs_p2p_ops_errors counter",
            ]
        )
        for kind, count in ops_errors.items():
            safe_kind = (
                str(kind)
                .replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("\n", " ")
            )
            lines.append(
                f"abs_p2p_ops_errors{{node_id=\"{node_id}\",kind=\"{safe_kind}\"}} "
                f"{int(count or 0)}"
            )
        lines.extend(
            [
                "# HELP abs_db_engine Storage engine label (rocksdb|sqlite|unknown)",
                "# TYPE abs_db_engine gauge",
                (
                    f"abs_db_engine{{node_id=\"{node_id}\","
                    f"engine=\"{str(rocksdb_tuning.get('engine') or 'unknown')}\"}} 1"
                ),
            ]
        )
        emit_rocks = str(rocksdb_tuning.get("engine") or "") == "rocksdb" or str(
            rocksdb_tuning.get("source") or ""
        ) in ("live", "config_fallback")
        if emit_rocks and str(rocksdb_tuning.get("engine") or "") != "sqlite":
            lines.extend(
                [
                    "# HELP abs_rocksdb_column_families Whether RocksDB column families are enabled",
                    "# TYPE abs_rocksdb_column_families gauge",
                    (
                        f"abs_rocksdb_column_families{{node_id=\"{node_id}\"}} "
                        f"{1 if rocksdb_tuning.get('column_families') else 0}"
                    ),
                    "# HELP abs_rocksdb_block_cache_mb RocksDB block cache size (MB)",
                    "# TYPE abs_rocksdb_block_cache_mb gauge",
                    (
                        f"abs_rocksdb_block_cache_mb{{node_id=\"{node_id}\"}} "
                        f"{int(rocksdb_tuning.get('block_cache_mb', 0) or 0)}"
                    ),
                    "# HELP abs_rocksdb_write_buffer_mb RocksDB write buffer size (MB)",
                    "# TYPE abs_rocksdb_write_buffer_mb gauge",
                    (
                        f"abs_rocksdb_write_buffer_mb{{node_id=\"{node_id}\"}} "
                        f"{int(rocksdb_tuning.get('write_buffer_mb', 0) or 0)}"
                    ),
                    "# HELP abs_rocksdb_json_decode_failures Corrupt RocksDB JSON rows skipped",
                    "# TYPE abs_rocksdb_json_decode_failures counter",
                    (
                        f"abs_rocksdb_json_decode_failures{{node_id=\"{node_id}\"}} "
                        f"{int(rocksdb_tuning.get('json_decode_failures', 0) or 0)}"
                    ),
                ]
            )
        lines.extend(
            [
                "# HELP abs_sqlite_json_decode_failures Corrupt SQLite/aux JSON rows skipped",
                "# TYPE abs_sqlite_json_decode_failures counter",
                (
                    f"abs_sqlite_json_decode_failures{{node_id=\"{node_id}\"}} "
                    f"{int(rocksdb_tuning.get('sqlite_json_decode_failures', 0) or 0)}"
                ),
                "# HELP abs_aux_json_decode_failures Corrupt hybrid aux.db JSON rows skipped",
                "# TYPE abs_aux_json_decode_failures counter",
                (
                    f"abs_aux_json_decode_failures{{node_id=\"{node_id}\"}} "
                    f"{int(rocksdb_tuning.get('aux_json_decode_failures', 0) or 0)}"
                ),
                "# HELP abs_ws_send_failures_total WebSocket outbound send failures",
                "# TYPE abs_ws_send_failures_total counter",
                (
                    f"abs_ws_send_failures_total{{node_id=\"{node_id}\"}} "
                    f"{int(ws_stats.get('send_failures', 0) or 0)}"
                ),
                "# HELP abs_ws_running Whether WebSocket server reports running",
                "# TYPE abs_ws_running gauge",
                (
                    f"abs_ws_running{{node_id=\"{node_id}\"}} "
                    f"{1 if ws_stats.get('running') else 0}"
                ),
            ]
        )
        lines.extend(
            [
                "# HELP abs_state_consistent Whether tip state root matches peers",
                "# TYPE abs_state_consistent gauge",
                (
                    f"abs_state_consistent{{node_id=\"{node_id}\"}} "
                    f"{1 if sync_status.get('state_consistent') else 0}"
                ),
                "# HELP abs_sync_wire_probe_ok Last peer state_root wire probe "
                "# (-1=never probed, 0=failed, 1=ok)",
                "# TYPE abs_sync_wire_probe_ok gauge",
                (
                    f"abs_sync_wire_probe_ok{{node_id=\"{node_id}\"}} "
                    f"{self._wire_probe_ok_gauge(sync_status)}"
                ),
                "# HELP abs_sync_wire_probe_probed Whether a wire probe has completed",
                "# TYPE abs_sync_wire_probe_probed gauge",
                (
                    f"abs_sync_wire_probe_probed{{node_id=\"{node_id}\"}} "
                    f"{1 if sync_status.get('wire_probe_probed') else 0}"
                ),
                "# HELP abs_rocksdb_tuning_source Whether live DB stats or config fallback",
                "# TYPE abs_rocksdb_tuning_source gauge",
                (
                    f"abs_rocksdb_tuning_source{{node_id=\"{node_id}\","
                    f"source=\"{str(rocksdb_tuning.get('source') or 'unknown')}\"}} 1"
                ),
                "# HELP abs_state_engine_available Deterministic StateEngine present",
                "# TYPE abs_state_engine_available gauge",
                (
                    f"abs_state_engine_available{{node_id=\"{node_id}\"}} "
                    f"{1 if core_engines.get('state_engine') else 0}"
                ),
                "# HELP abs_finality_engine_available FinalityEngine (Casper FFG) present",
                "# TYPE abs_finality_engine_available gauge",
                (
                    f"abs_finality_engine_available{{node_id=\"{node_id}\"}} "
                    f"{1 if core_engines.get('finality_engine') else 0}"
                ),
                "# HELP abs_ims_available ImmutableStateManager present",
                "# TYPE abs_ims_available gauge",
                (
                    f"abs_ims_available{{node_id=\"{node_id}\"}} "
                    f"{1 if core_engines.get('immutable_state') else 0}"
                ),
            ]
        )
        for kernel in native_crypto.get("kernels", []):
            safe_kernel = str(kernel).replace("\\", "\\\\").replace('"', '\\"')
            lines.append(
                f"abs_native_crypto_kernel_enabled{{node_id=\"{node_id}\",kernel=\"{safe_kernel}\"}} 1"
            )
        return "\n".join(lines) + "\n"

    @staticmethod
    def _wire_probe_ok_gauge(sync_status: Optional[dict[str, Any]]) -> int:
        """Prometheus value: -1 never probed, 0 failed, 1 ok."""
        status = sync_status or {}
        if not bool(status.get("wire_probe_probed")):
            return -1
        return 1 if bool(status.get("wire_probe_ok")) else 0
