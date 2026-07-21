#!/usr/bin/env python3
"""Industrial readiness gate — code-level checks without external audit blockers."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _check_p2p_hardening() -> tuple[list[str], list[str]]:
    """Static P2P industrial surface checks (no live mesh required)."""
    errors: list[str] = []
    warnings: list[str] = []
    from network.p2p_node import (
        ALLOWED_WIRE_TYPES,
        DEFAULT_MAX_P2P_LINE_BYTES,
        P2PNode,
        RATE_LIMIT_EXEMPT_TYPES,
    )
    from runtime.config import Config

    required_types = {
        "handshake",
        "handshake_ack",
        "new_block",
        "block",
        "blocks",
        "status",
        "state_root_request",
        "state_root_response",
    }
    missing = required_types - ALLOWED_WIRE_TYPES
    if missing:
        errors.append(f"P2P allowlist missing types: {sorted(missing)}")
    required_exempt = {
        "new_block",
        "get_block",
        "get_blocks",
        "block",
        "blocks",
        "new_tx",
        "status",
    }
    missing_exempt = required_exempt - RATE_LIMIT_EXEMPT_TYPES
    if missing_exempt:
        errors.append(f"P2P rate-limit exempt set missing sync types: {sorted(missing_exempt)}")

    cfg = Config()
    if int(getattr(cfg, "p2p_max_message_bytes", 0) or 0) < DEFAULT_MAX_P2P_LINE_BYTES // 2:
        warnings.append("p2p_max_message_bytes lower than industrial default")
    if int(getattr(cfg, "p2p_max_messages_per_sec", 0) or 0) <= 0:
        warnings.append("p2p_max_messages_per_sec disabled (0)")
    for attr in ("get_p2p_security_status", "_maintenance_loop", "_strike_peer_sync"):
        if not hasattr(P2PNode, attr):
            errors.append(f"P2PNode missing {attr}")
    import inspect

    p2p_src = inspect.getsource(P2PNode)
    for needle in ("shape_rejects_total", "_shape_reject_counts", "WireReject"):
        if needle not in p2p_src:
            errors.append(f"P2PNode missing industrial observability: {needle}")
    p2p_mod = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    for needle in (
        "class WireReject",
        "bad_wire_line",
        "p2p_line_too_large",
        "rate_limit_exceeded",
        "recv_error",
        "_housekeeping_payload_ok",
        "peer_send_fail",
        "mid_session_handshake",
    ):
        if needle not in p2p_mod:
            errors.append(f"p2p_node.py missing wire-reject surface: {needle}")
    http_src = (ROOT / "api" / "http.py").read_text(encoding="utf-8")
    for needle in (
        "shape_rejects_total",
        "rate_limit_drops",
        "_status_p2p_hardening_snapshot",
    ):
        if needle not in http_src:
            errors.append(f"api/http.py missing status honesty surface: {needle}")
    metrics_src = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    for needle in (
        "abs_p2p_shape_rejects_total",
        "abs_p2p_shape_rejects",
        "abs_p2p_handshake_rejects_total",
        "abs_p2p_active_bans",
        "abs_p2p_rate_limit_drops_total",
        "abs_p2p_peer_send_fail_total",
        "abs_p2p_ops_errors",
        "abs_p2p_attestation_local_fail_total",
        "abs_p2p_peer_tx_reject_total",
        "abs_rocksdb_column_families",
        "abs_db_engine",
        "abs_state_consistent",
        "abs_sync_wire_probe_ok",
        "abs_sync_wire_probe_probed",
    ):
        if needle not in metrics_src:
            errors.append(f"metrics.py missing Prometheus series: {needle}")
    for needle in (
        "maintenance_loop_fail",
        "catch_up_loop_fail",
        "strike %s/%s",
        "peer_tx_reject",
        "bad_peer_tx",
        "import_block_fail",
        "sync_fail",
        "discovery_loop_fail",
    ):
        if needle not in p2p_mod:
            errors.append(f"p2p_node.py missing industrial surface: {needle}")
    alerts_src = (ROOT / "deploy" / "prometheus" / "alerts.yml").read_text(encoding="utf-8")
    for needle in (
        "abs_p2p_shape_rejects_total",
        "abs_p2p_rate_limit_drops_total",
        "abs_p2p_peer_send_fail_total",
        "abs_p2p_handshake_rejects_total",
        "abs_p2p_ops_errors",
        "abs_p2p_attestation_local_fail_total",
        "abs_p2p_peer_tx_reject_total",
        "abs_rocksdb_block_cache_mb",
        "abs_state_consistent",
        "abs_sync_wire_probe_ok",
    ):
        if needle not in alerts_src:
            errors.append(f"prometheus alerts.yml missing rule surface: {needle}")
    dash_src = (ROOT / "deploy" / "grafana" / "dashboard.json").read_text(encoding="utf-8")
    for needle in (
        "abs_p2p_peer_send_fail_total",
        "abs_p2p_ops_errors",
        "mid_session_handshake",
        "abs_p2p_attestation_local_fail_total",
        "abs_p2p_peer_tx_reject_total",
        "abs_state_consistent",
        "abs_sync_wire_probe_ok",
    ):
        if needle not in dash_src:
            errors.append(f"grafana dashboard.json missing panel surface: {needle}")
    try:
        from network import p2p_tls  # noqa: F401
    except ImportError as exc:
        errors.append(f"network.p2p_tls import failed: {exc}")
    # Load real prod mesh JSON (bare Config() is always deployment_mode=dev).
    prod_tls_enabled = False
    prod_json_files = (
        "docker/node.prod.mesh1.json",
        "docker/node.prod.mesh2.json",
        "docker/node.prod.mesh3.json",
        "docker/node.prod.json",
        "deploy/k8s/node.prod.k8s.json",
        "node.prod.example.json",
        "node.prod.mainnet-v1.example.json",
        "node.prod.mainnet-v1.bridge.example.json",
    )
    shared_keys = (
        "p2p_max_messages_per_sec",
        "p2p_max_message_bytes",
        "p2p_ban_seconds",
        "p2p_rate_limit_strikes",
        "p2p_evict_min_score",
        "rocksdb_sync",
        "rocksdb_block_cache_mb",
        "rocksdb_write_buffer_mb",
        "rocksdb_column_families",
        "bridge_enabled",
        "require_native_crypto",
        "state_root_legacy_cutoff_height",
        "rust_bridge_path",
        "bridge_auto_confirm_sec",
    )
    mesh_json_cfgs: list[tuple[str, dict]] = []
    for rel in prod_json_files:
        path = ROOT / rel
        if not path.is_file():
            continue
        try:
            prod_cfg = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(prod_cfg.get("deployment_mode", "")).lower() != "prod":
            continue
        for key in shared_keys:
            if key not in prod_cfg:
                errors.append(f"{rel}: missing industrial key {key}")
        rate = int(prod_cfg.get("p2p_max_messages_per_sec", 0) or 0)
        if rate <= 0:
            errors.append(f"{rel}: p2p_max_messages_per_sec must be > 0")
        max_bytes = int(prod_cfg.get("p2p_max_message_bytes", 0) or 0)
        if max_bytes and max_bytes < DEFAULT_MAX_P2P_LINE_BYTES // 2:
            errors.append(
                f"{rel}: p2p_max_message_bytes below industrial floor "
                f"({DEFAULT_MAX_P2P_LINE_BYTES // 2})"
            )
        if prod_cfg.get("bridge_enabled") is True:
            if "bridge" in Path(rel).name.lower():
                warnings.append(
                    f"{rel}: bridge_enabled=true (cutover example only; keep OFF on live mesh)"
                )
            else:
                errors.append(f"{rel}: bridge_enabled must be false until L1 audit")
        if prod_cfg.get("p2p_tls_enabled") is True:
            prod_tls_enabled = True
        mesh_min = int(prod_cfg.get("mesh_min_peers_before_mine", 0) or 0)
        needs_redis = mesh_min >= 1 or "k8s" in Path(rel).name.lower()
        if needs_redis:
            if "redis_rate_limit_enabled" not in prod_cfg or "redis_url" not in prod_cfg:
                errors.append(f"{rel}: mesh/k8s requires redis_rate_limit_enabled + redis_url")
            elif prod_cfg.get("redis_rate_limit_enabled") is not True:
                errors.append(f"{rel}: redis_rate_limit_enabled must be true for mesh/k8s")
            elif not str(prod_cfg.get("redis_url") or "").strip():
                errors.append(f"{rel}: redis_url must be non-empty for mesh/k8s")
        if "mesh" in Path(rel).name.lower():
            mesh_json_cfgs.append((rel, prod_cfg))
    # Compose env freeze vs prod JSON (3-node mesh + single-node).
    import re

    def _compose_default(compose_text: str, env_key: str) -> str | None:
        m = re.search(
            rf"(?m)^\s*{re.escape(env_key)}:\s*(.+?)\s*$",
            compose_text,
        )
        if not m:
            return None
        raw = m.group(1).strip().strip('"').strip("'")
        dm = re.match(r"^\$\{[^:]+:-([^}]+)\}$", raw)
        if dm:
            return dm.group(1).strip().strip('"').strip("'")
        return raw

    def _freeze_compose_json(
        compose_rel: str,
        json_cfgs: list[tuple[str, dict]],
        env_map: dict[str, str],
    ) -> None:
        compose_path = ROOT / compose_rel
        if not compose_path.is_file() or not json_cfgs:
            return
        compose_text = compose_path.read_text(encoding="utf-8")
        for env_key, json_key in env_map.items():
            compose_val = _compose_default(compose_text, env_key)
            if compose_val is None:
                errors.append(f"{compose_rel} missing {env_key}")
                continue
            for rel, prod_cfg in json_cfgs:
                if json_key not in prod_cfg:
                    continue
                raw = prod_cfg.get(json_key)
                if isinstance(raw, bool):
                    json_val = "true" if raw else "false"
                else:
                    json_val = str(raw).strip()
                if compose_val.lower() != json_val.lower():
                    errors.append(
                        f"compose↔JSON mismatch {compose_rel} {env_key}={compose_val} vs "
                        f"{rel}.{json_key}={json_val}"
                    )

    shared_compose_env = {
        "ROCKSDB_SYNC": "rocksdb_sync",
        "ROCKSDB_BLOCK_CACHE_MB": "rocksdb_block_cache_mb",
        "ROCKSDB_WRITE_BUFFER_MB": "rocksdb_write_buffer_mb",
        "ROCKSDB_COLUMN_FAMILIES": "rocksdb_column_families",
        "P2P_MAX_MESSAGE_BYTES": "p2p_max_message_bytes",
        "P2P_MAX_MESSAGES_PER_SEC": "p2p_max_messages_per_sec",
        "P2P_BAN_SECONDS": "p2p_ban_seconds",
        "P2P_RATE_LIMIT_STRIKES": "p2p_rate_limit_strikes",
        "P2P_EVICT_MIN_SCORE": "p2p_evict_min_score",
        "BRIDGE_ENABLED": "bridge_enabled",
        "DB_ENGINE": "db_engine",
        "JWT_ENFORCE_ADMIN": "jwt_enforce_admin",
    }
    mesh_env = dict(shared_compose_env)
    mesh_env["REDIS_RATE_LIMIT"] = "redis_rate_limit_enabled"
    mesh_env["REDIS_URL"] = "redis_url"
    _freeze_compose_json("docker-compose.prod.3node.yml", mesh_json_cfgs, mesh_env)

    single_json: list[tuple[str, dict]] = []
    single_path = ROOT / "docker" / "node.prod.json"
    if single_path.is_file():
        try:
            single_cfg = json.loads(single_path.read_text(encoding="utf-8"))
            if str(single_cfg.get("deployment_mode", "")).lower() == "prod":
                single_json.append(("docker/node.prod.json", single_cfg))
        except (OSError, json.JSONDecodeError):
            pass
    _freeze_compose_json("docker-compose.prod.yml", single_json, shared_compose_env)

    for overlay in (
        "docker-compose.prod.p2ptls.yml",
        "docker-compose.prod.3node.p2ptls.yml",
    ):
        overlay_path = ROOT / overlay
        if not overlay_path.is_file():
            errors.append(f"missing {overlay}")
            continue
        overlay_txt = overlay_path.read_text(encoding="utf-8")
        for needle in (
            "P2P_TLS_ENABLED",
            "P2P_TLS_FAIL_CLOSED",
            "P2P_TLS_BIND_IDENTITY",
            "P2P_TLS_REQUIRE_CLIENT_CERT",
        ):
            if needle not in overlay_txt:
                errors.append(f"{overlay} missing {needle}")

    env_ex = ROOT / ".env.example"
    if env_ex.is_file():
        env_txt = env_ex.read_text(encoding="utf-8")
        if "778888" not in env_txt:
            errors.append(".env.example must document mainnet CHAIN_ID 778888")
        if "CHAIN_ID=77777" not in env_txt and "CHAIN_ID=778888" not in env_txt:
            errors.append(".env.example missing CHAIN_ID example value")
        if "ENABLE_CORS_RPC_PROXY=false" not in env_txt:
            errors.append(".env.example must default ENABLE_CORS_RPC_PROXY=false")
        if "CORS_ORIGINS=*" in env_txt:
            errors.append(".env.example must not default CORS_ORIGINS=*")
    main_py = (ROOT / "main.py").read_text(encoding="utf-8")
    if 'Access-Control-Allow-Origin", "*"' in main_py or "Access-Control-Allow-Origin', '*'" in main_py:
        errors.append("main.py CORS RPC proxy must not hardcode Allow-Origin *")
    if "prod CORS RPC proxy requires explicit CORS_ORIGINS" not in main_py:
        errors.append("main.py must refuse prod CORS proxy with wildcard origins")
    rocks_py = (ROOT / "storage" / "rocks_store.py").read_text(encoding="utf-8")
    if "reorg_truncate_above: corrupt block JSON" not in rocks_py:
        errors.append("rocks_store.reorg_truncate_above must log corrupt block JSON")
    if "corrupt tx JSON" not in rocks_py:
        errors.append("rocks_store.reorg must log corrupt tx JSON")
    if "corrupt tx_propagation JSON" not in rocks_py:
        errors.append("rocks_store.reorg purge must log corrupt tx_propagation JSON")
    if "rocksdb_properties_error" not in rocks_py:
        errors.append("rocks_store.get_stats must surface rocksdb_properties_error")
    db_py = (ROOT / "storage" / "database.py").read_text(encoding="utf-8")
    if "DELETE FROM evm_logs WHERE block_height" not in db_py:
        errors.append("SQLite reorg_truncate_above must delete evm_logs")
    if "DELETE FROM tx_propagation_events WHERE block_height" not in db_py:
        errors.append("SQLite reorg_truncate_above must delete tx_propagation_events")
    if "def truncate_blocks_above" in db_py and "truncate_chain_state(height)" not in db_py:
        errors.append("SQLite truncate_blocks_above must call truncate_chain_state")
    if "def _normalize_tx_status" not in db_py:
        errors.append("SQLite must define _normalize_tx_status")
    if "Missing/unknown → 0 (fail-closed)" not in db_py:
        errors.append("SQLite _normalize_tx_status must fail-closed on missing/unknown")
    http_py = (ROOT / "api" / "http.py").read_text(encoding="utf-8")
    if 'origins else "*"' in http_py:
        errors.append("api/http.py REST CORS must not fall back to *")
    health_py = (ROOT / "bridge" / "health.py").read_text(encoding="utf-8")
    if "probe_skipped" not in health_py:
        errors.append("bridge.health must mark unprobed L1 as probe_skipped")
    metrics_py = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    if "abs_l1_rpc_probed" not in metrics_py:
        errors.append("metrics.py missing abs_l1_rpc_probed")
    if not prod_tls_enabled:
        warnings.append(
            "prod mesh JSON: p2p_tls_enabled is not true "
            "(enable TLS overlay / -P2pTls for public mainnet wire)"
        )
    return errors, warnings


def _check_fail_loud_surfaces() -> tuple[list[str], list[str]]:
    """Static inspect: prod-critical paths must not silent-pass probe/meta failures."""
    import inspect

    errors: list[str] = []
    warnings: list[str] = []
    http_py = (ROOT / "api" / "http.py").read_text(encoding="utf-8")
    try:
        from sync.sync_engine import SyncEngine

        src = inspect.getsource(SyncEngine.sync_state)
        if "peer state_root wire probe failed" not in src:
            errors.append("SyncEngine.sync_state must log wire probe failures")
        if "wire probe empty" not in src and "empty with" not in src:
            errors.append("SyncEngine.sync_state must fail-closed on empty probe with peers")
        if "missing get_state_root" not in src:
            errors.append("SyncEngine.sync_state must fail-closed when get_state_root missing")
        status_src = inspect.getsource(SyncEngine.get_status)
        if "wire_probe_ok" not in status_src:
            errors.append("SyncEngine.get_status missing wire_probe_ok")
        if "wire_probe_probed" not in status_src:
            errors.append("SyncEngine.get_status missing wire_probe_probed")
    except Exception as exc:
        errors.append(f"fail-loud sync inspect failed: {exc}")
    try:
        from blockchain.immutable_state import ImmutableStateManager

        src = inspect.getsource(ImmutableStateManager.reconcile_from_store)
        if "fail_loud" not in src:
            errors.append("IMS reconcile_from_store missing fail_loud")
        if "except Exception:\n                        pass" in src or "except Exception:\n                            pass" in src:
            errors.append("IMS reconcile_from_store still has silent except pass")
    except Exception as exc:
        errors.append(f"fail-loud IMS inspect failed: {exc}")
    try:
        main_py = (ROOT / "main.py").read_text(encoding="utf-8")
        if "sync_state probe failed" not in main_py:
            errors.append("main.py mining loop must log sync_state probe failures")
        try:
            src = inspect.getsource(SyncEngine.fast_sync)
            if "return bool(self.sync_state())" not in src and "self.sync_state()" not in src:
                errors.append("SyncEngine.fast_sync must re-check consistency via sync_state()")
        except Exception as exc:
            errors.append(f"SyncEngine.fast_sync inspect failed: {exc}")
        if "db_probe_error" not in http_py or "/health/ready" not in http_py:
            errors.append("/health/ready must probe database and surface db_probe_error")
        if "self.p2p._state_consistent = False" not in main_py:
            errors.append("main.py must clear _state_consistent on sync probe failure")
        for needle in (
            "[Mining] PBS auction failed",
            "[Mining] cross-shard processing failed",
            "[Mining] epoch pool unlock failed",
        ):
            if needle not in main_py:
                errors.append(f"main.py mining loop must log: {needle}")
        if "p2p.sync_engine = self.sync_engine" not in main_py:
            errors.append("main.py must share AbsoluteNode SyncEngine with P2P")
        if "shared with P2P" not in main_py:
            errors.append("main.py must log SyncEngine shared with P2P")
    except Exception as exc:
        errors.append(f"fail-loud main.py inspect failed: {exc}")
    try:
        http_py = (ROOT / "api" / "http.py").read_text(encoding="utf-8")
        if 'checks["p2p_running"]' not in http_py and "p2p_running" not in http_py:
            errors.append("/health/ready must check p2p_running in prod")
        if 'after.get("state_consistent", False)' not in http_py:
            errors.append("fork recovery must default state_consistent=False (fail-closed)")
        if "never echo first allowlist entry" not in http_py:
            errors.append("CORS must never echo first allowlist entry on miss")
        if "empty cors_origins must not promote to *" not in http_py:
            errors.append("CORS empty allowlist must not promote to *")
        if 'success = bool(repaired) and harness_ok and consistent' not in http_py:
            errors.append(
                "/chain/consistency/repair success must require repair+harness+consistent"
            )
        if 'if peer_count > 0:' not in http_py or 'checks["state_consistent"]' not in http_py:
            errors.append("/health/ready with peers must require state_consistent")
        if 'checks["peer_count_probe"] = False' not in http_py:
            errors.append("/health/ready peer_count probe failure must fail-closed")
        if 'p2p_fallback' not in http_py or "SyncEngine missing" not in http_py:
            errors.append("p2p_fallback sync status must fail-closed when SyncEngine missing")
        if "Database._normalize_tx_status(tx.get(\"status\"))" not in http_py:
            errors.append("receipt format must normalize omitted status fail-closed to 0")
        if '"bridge_relayer_live": bool(cfg.bridge_enabled)' in http_py:
            errors.append("bridge_relayer_live must not equal bridge_enabled alone")
        if '"bridge_rust_binary_healthy"' not in http_py:
            errors.append("core_real must expose bridge_rust_binary_healthy separately from relayer_live")
        if '"relayer_observed"' not in http_py:
            errors.append("core_real must expose relayer_observed honesty flag")
        if 'and bool(bridge_health.get("ok"))' not in http_py:
            errors.append("bridge_rust_binary_healthy must require rust bridge health ok")
        if '"bridge_relayer_live": False' not in http_py:
            errors.append("bridge_relayer_live must stay false until relayer heartbeat observed")
        if 'out["error"] = "bridge_disabled"' not in http_py:
            errors.append("_rust_bridge_health must fail-closed when bridge disabled")
        if "json_decode_failures" not in (
            ROOT / "storage" / "rocks_store.py"
        ).read_text(encoding="utf-8"):
            errors.append("rocks_store must expose json_decode_failures for /metrics")
        if "Config-on ≠ actively forging under mesh gate" not in http_py:
            errors.append("eth_mining must gate on mesh_min_peers / state_consistent")
        if 'checks["wire_probe_probed"]' not in http_py or 'checks["wire_probe_ok"]' not in http_py:
            errors.append("/health/ready with peers must require wire_probe_probed/ok")
        if '"degraded"' not in http_py or "peer_count > 0 and not state_consistent" not in http_py:
            errors.append("/status must report degraded when peers + inconsistent")
        if "peer_count > 0 and not wire_probe_probed" not in http_py:
            errors.append("/status must report degraded when peers + never wire-probed")
        if 'checks["state_engine"]' not in http_py or 'checks["finality_engine"]' not in http_py:
            errors.append("/health/ready prod must check state_engine and finality_engine")
        if 'checks["immutable_state"]' not in http_py:
            errors.append("/health/ready prod must check immutable_state")
        if '"ims_available": False' not in http_py:
            errors.append("abs-balance/total-supply must not claim canonical without IMS")
        if '"finality_quorum_live": False' not in http_py:
            errors.append("core_real must not invent finality_quorum_live from local attest count")
        if '"local_attestations_present"' not in http_py:
            errors.append("core_real must expose local_attestations_present separately from quorum")
        if '"state_engine": self.__class__.state_engine is not None' not in http_py:
            errors.append("core_real must expose state_engine availability")
        if "finality_engine_missing" not in http_py:
            errors.append("/finality/stats must surface finality_engine_missing error")
        if "state_engine_missing" not in http_py:
            errors.append("/state/engine must surface state_engine_missing error")
        if "DB-only is never IMS-canonical when shadow state is absent/unusable" not in http_py:
            errors.append("/state/supply must not claim DB-only canonical")
        if "Peers present with mesh_min=0" not in http_py:
            errors.append("eth_mining must refuse when peers present and inconsistent (mesh_min=0)")
        if 'getattr(p2p, "_server", None) is not None' not in http_py:
            errors.append("/health/ready p2p_running must require bound _server")
    except Exception as exc:
        errors.append(f"fail-loud http inspect failed: {exc}")
    try:
        rocks_py = (ROOT / "storage" / "rocks_store.py").read_text(encoding="utf-8")
        if rocks_py.count("self._json_decode_failures += 1") < 15:
            errors.append("rocks_store scan/reorg/list/meta/tx paths must bump json_decode_failures")
        if "corrupt meta" not in rocks_py:
            errors.append("rocks_store get_meta must warn on corrupt decode")
        if "corrupt address_tx row skipped" not in rocks_py:
            errors.append("rocks_store address tx list must warn on corrupt decode")
        if "corrupt recent_tx row skipped" not in rocks_py:
            errors.append("rocks_store recent tx list must warn on corrupt decode")
        if "corrupt latest_block row skipped" not in rocks_py:
            errors.append("rocks_store get_latest_blocks must warn on corrupt decode")
        if "corrupt account row skipped" not in rocks_py:
            errors.append("rocks_store get_all_accounts must warn on corrupt decode")
        if "corrupt validator row skipped" not in rocks_py:
            errors.append("rocks_store get_validators must warn on corrupt decode")
        if "corrupt proposer_audit row skipped" not in rocks_py:
            errors.append("rocks_store proposer_audit must warn on corrupt decode")
        if "corrupt bridge_lock row skipped" not in rocks_py:
            errors.append("rocks_store bridge_locks must warn on corrupt decode")
        if "corrupt state_root_mismatch row skipped" not in rocks_py:
            errors.append("rocks_store state_root mismatches must warn on corrupt decode")
    except Exception as exc:
        errors.append(f"fail-loud rocks_store inspect failed: {exc}")
    try:
        metrics_py = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
        if "abs_rocksdb_json_decode_failures" not in metrics_py:
            errors.append("metrics.py must emit abs_rocksdb_json_decode_failures")
        alerts = (ROOT / "deploy" / "prometheus" / "alerts.yml").read_text(encoding="utf-8")
        if "AbsoluteRocksJsonDecodeFailures" not in alerts:
            errors.append("alerts.yml missing AbsoluteRocksJsonDecodeFailures")
        if "AbsoluteProdCoreEngineMissing" not in alerts:
            errors.append("alerts.yml missing AbsoluteProdCoreEngineMissing")
        if "abs_state_engine_available" not in metrics_py:
            errors.append("metrics.py must emit abs_state_engine_available")
        if "abs_finality_engine_available" not in metrics_py:
            errors.append("metrics.py must emit abs_finality_engine_available")
        if "abs_ims_available" not in metrics_py:
            errors.append("metrics.py must emit abs_ims_available")
    except Exception as exc:
        errors.append(f"fail-loud rocks metrics/alerts inspect failed: {exc}")
    try:
        sync_py = (ROOT / "sync" / "sync_engine.py").read_text(encoding="utf-8")
        if "Solo / no peers — wire probe deferred (never-probed), fail-closed" not in sync_py:
            errors.append("sync_state solo must fail-closed and clear consistency")
        if "No same-height peer root match — fail-closed" not in sync_py:
            errors.append("sync_state must require same-height peer root match before True")
    except Exception as exc:
        errors.append(f"fail-loud sync_engine inspect failed: {exc}")
    try:
        mesh_py = (ROOT / "runtime" / "mesh_mining.py").read_text(encoding="utf-8")
        if "return bool(state_consistent)" not in mesh_py:
            errors.append("mesh_ready_for_mining peer_heights path must gate on state_consistent")
        if "state_consistent: bool = False" not in mesh_py:
            errors.append("mesh_ready_for_mining state_consistent default must be False")
    except Exception as exc:
        errors.append(f"fail-loud mesh_mining inspect failed: {exc}")
    try:
        bridge_health_py = (ROOT / "bridge" / "health.py").read_text(encoding="utf-8")
        if '"ok": False' not in bridge_health_py or "no L1 RPC URLs configured" not in bridge_health_py:
            errors.append("L1 health must default ok=False when unconfigured")
    except Exception as exc:
        errors.append(f"fail-loud bridge health inspect failed: {exc}")
    try:
        main_py = (ROOT / "main.py").read_text(encoding="utf-8")
        if "never echo first allowlist entry" not in main_py:
            errors.append("RPC CORS proxy must never echo first allowlist entry on miss")
        if "Production mode requires SyncEngine" not in main_py:
            errors.append("main.py must hard-fail SyncEngine init in production")
        if "Production mode requires StateEngine" not in main_py:
            errors.append("main.py must hard-fail StateEngine init in production")
        if "Production mode requires FinalityEngine" not in main_py:
            errors.append("main.py must hard-fail FinalityEngine init in production")
        if "Production mode requires ImmutableStateManager" not in main_py:
            errors.append("main.py must hard-fail ImmutableStateManager missing in production")
        if "Production mode requires block signature" not in main_py:
            errors.append("main.py must hard-fail block signing failures in production")
        if "Peers present require consistency even when mesh_min_peers_before_mine=0" not in main_py:
            errors.append("mining loop must gate consistency when peers present (mesh_min=0)")
    except Exception as exc:
        errors.append(f"fail-loud main CORS inspect failed: {exc}")
    try:
        p2p_py = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
        if "self._state_consistent = False" not in p2p_py:
            errors.append("P2PNode must boot with _state_consistent=False")
        if "Unsolicited state_root match" not in p2p_py:
            errors.append("P2P unsolicited state_root match must not flip consistent=True")
        if "State root mismatch vs" not in p2p_py:
            errors.append("P2P unsolicited state_root mismatch must clear consistent")
        if "Sync incomplete" not in p2p_py:
            errors.append("P2P sync must log Sync incomplete (not claim complete on stall)")
        if "reached_target" not in p2p_py:
            errors.append("P2P sync must gate state_root baseline on reached_target")
        if "consistent_ok = bool(self._state_consistent) if peers else True" not in p2p_py:
            errors.append("topology_healthy must require state_consistent when peers present")
        if "Reconcile \"ok\" without a SyncEngine must not leave stale mesh-green" not in p2p_py:
            errors.append("reconcile_peers without SyncEngine must clear _state_consistent")
        if "_record_broadcast_results" not in p2p_py or "broadcast_fail" not in p2p_py:
            errors.append("P2P broadcast gather must record False/Exception as broadcast_fail")
        for kind in (
            'kind="cross_shard_ack"',
            'kind="cross_shard_tx"',
            'kind="shard_migration"',
            'kind="validator_register"',
            'kind="catch_up_sync"',
        ):
            if kind not in p2p_py:
                errors.append(f"P2P must record broadcast results for {kind}")
        bind_idx = p2p_py.find("Could not bind port")
        if bind_idx < 0:
            errors.append("P2P start must log Could not bind port")
        else:
            bind_snip = p2p_py[bind_idx : bind_idx + 320]
            if "self._running = False" not in bind_snip or "return" not in bind_snip:
                errors.append("P2P bind failure must set _running=False and return")
    except Exception as exc:
        errors.append(f"fail-loud p2p inspect failed: {exc}")
    try:
        rocks_py = (ROOT / "storage" / "rocks_store.py").read_text(encoding="utf-8")
        if "_loads_json_or_none" not in rocks_py:
            errors.append("rocks_store must use _loads_json_or_none for point-get honesty")
        if 'return self._loads_json_or_none(raw, context=f"tx' not in rocks_py:
            errors.append("rocks_store get_transaction must use fail-closed JSON decode")
        if 'return self._loads_json_or_none(raw, context=f"receipt' not in rocks_py:
            errors.append("rocks_store get_tx_receipt must use fail-closed JSON decode")
        if 'return self._loads_json_or_none(raw, context=f"block' not in rocks_py:
            errors.append("rocks_store get_block must use fail-closed JSON decode")
        if 'context=f"slash_validator' not in rocks_py:
            errors.append("rocks_store slash_validator must use fail-closed JSON decode")
        if 'context=f"bridge_lock' not in rocks_py:
            errors.append("rocks_store confirm_bridge_lock must use fail-closed JSON decode")
        if 'context="burn_total"' not in rocks_py:
            errors.append("rocks_store get_total_burned must use fail-closed JSON decode")
        if 'context="tx_propagation"' not in rocks_py:
            errors.append("rocks_store tx_propagation decode must use fail-closed JSON decode")
        if 'context="evm_log"' not in rocks_py:
            errors.append("rocks_store evm_log decode must use fail-closed JSON decode")
        if 'context="nft_token"' not in rocks_py:
            errors.append("rocks_store nft_token decode must use fail-closed JSON decode")
        # get_meta corrupt path must return default, not garbage string
        if "Fail-closed: never return a garbage string as valid meta" not in rocks_py:
            errors.append("rocks_store get_meta must return default on corrupt decode")
    except Exception as exc:
        errors.append(f"fail-loud rocks point-get inspect failed: {exc}")
    try:
        alerts = (ROOT / "deploy" / "prometheus" / "alerts.yml").read_text(encoding="utf-8")
        if "AbsoluteP2PBroadcastFailBurst" not in alerts:
            errors.append("alerts.yml missing AbsoluteP2PBroadcastFailBurst")
        if "AbsoluteP2PPeerSyncFailBurst" not in alerts:
            errors.append("alerts.yml missing AbsoluteP2PPeerSyncFailBurst")
        if "AbsoluteP2PCatchUpLoopFailBurst" not in alerts:
            errors.append("alerts.yml missing AbsoluteP2PCatchUpLoopFailBurst")
    except Exception as exc:
        errors.append(f"fail-loud broadcast alert inspect failed: {exc}")
    try:
        main_py = (ROOT / "main.py").read_text(encoding="utf-8")
        if "forge still uses blockchain.create_block — not wired" not in main_py:
            errors.append("BlockBuilder must not advertise enabled when forge path is unwired")
    except Exception as exc:
        errors.append(f"fail-loud BlockBuilder honesty inspect failed: {exc}")
    try:
        http_py = (ROOT / "api" / "http.py").read_text(encoding="utf-8")
        if "consensus_adapter_missing" not in http_py:
            errors.append("/consensus/attestations must surface consensus_adapter_missing")
        if "slashing_engine_missing" not in http_py:
            errors.append("/slashing/status must surface slashing_engine_missing")
        if "sharding_missing" not in http_py:
            errors.append("/sharding/pending must surface sharding_missing")
        if "immutable_state_missing" not in http_py:
            errors.append("/state/stats|/state/all must surface immutable_state_missing")
        if "smart_accounts_missing" not in http_py:
            errors.append("unbound smart-account endpoints must surface smart_accounts_missing")
        if "sync_engine_missing" not in http_py:
            errors.append("/sync/peers must surface sync_engine_missing")
        if "contract_manager_missing" not in http_py:
            errors.append("/contracts must surface contract_manager_missing")
        if "peer_count > 0 and not sync_engine_bound" not in http_py:
            errors.append("/status must degrade when peers present without SyncEngine")
        if 'mode in ("prod", "production", "staging")' not in http_py:
            errors.append("eth_mining must refuse prod claim without P2P")
        if 'raise ValueError("eth filters unavailable")' not in http_py:
            errors.append("eth_getFilterChanges/Logs must raise when filters unbound")
        if '"websocket_send_failures"' not in http_py:
            errors.append("/status subsystems must expose websocket_send_failures")
    except Exception as exc:
        errors.append(f"fail-loud api missing-error inspect failed: {exc}")
    try:
        ws_py = (ROOT / "network" / "websocket.py").read_text(encoding="utf-8")
        if "broadcast send failed" not in ws_py:
            errors.append("WebSocket _broadcast must count/log send failures")
        if "Fail-closed: bind/runtime failure must not leave a live flag" not in ws_py:
            errors.append("WebSocket start must clear _running on bind/runtime failure")
        mh_py = (ROOT / "network" / "p2p" / "message_handler.py").read_text(encoding="utf-8")
        if "_send_failures" not in mh_py or "_send_unbound" not in mh_py:
            errors.append("legacy MessageHandler._send must count unbound/send failures")
        clone_py = (ROOT / "storage" / "chain_clone.py").read_text(encoding="utf-8")
        if "Fail-closed: when RocksEngine is available" not in clone_py:
            errors.append("chain_clone must fail-closed on Rocks checkpoint when native present")
        db_py = (ROOT / "storage" / "database.py").read_text(encoding="utf-8")
        if "_loads_json_or_none" not in db_py or "json_decode_failures" not in db_py:
            errors.append("SQLite Database must fail-closed JSON decode with counter")
        if 'context="plasma_txs"' not in db_py or 'context="nft_token_meta"' not in db_py:
            errors.append("SQLite feature tables must use counted JSON decode")
        amount_py = (ROOT / "runtime" / "amount.py").read_text(encoding="utf-8")
        if "_native_fallback" not in amount_py or "REQUIRE_NATIVE_CRYPTO" not in amount_py:
            errors.append("amount.py must fail-closed when REQUIRE_NATIVE_CRYPTO is set")
        p2p_py = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
        if "expected = max(1, mesh_min)" not in p2p_py:
            errors.append("topology_healthy must require peers in prod/staging")
        hyb_py = (ROOT / "storage" / "hybrid_database.py").read_text(encoding="utf-8")
        if "skipped_corrupt" not in hyb_py:
            errors.append("hybrid aux migrate must skip corrupt JSON without inventing empties")
        if "aux_json_decode_failures" not in hyb_py:
            errors.append("hybrid get_stats must expose aux_json_decode_failures")
        backup_py = (ROOT / "storage" / "chain_backup.py").read_text(encoding="utf-8")
        if "never invent tip 0 as success" not in backup_py:
            errors.append("read_chain_tip must fail-closed on corrupt/missing storage")
        metrics_py = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
        if "abs_sqlite_json_decode_failures" not in metrics_py:
            errors.append("metrics must export abs_sqlite_json_decode_failures")
        if "abs_ws_send_failures_total" not in metrics_py:
            errors.append("metrics must export abs_ws_send_failures_total")
        alerts = (ROOT / "deploy" / "prometheus" / "alerts.yml").read_text(encoding="utf-8")
        if "AbsoluteSqliteJsonDecodeFailures" not in alerts:
            errors.append("alerts.yml missing AbsoluteSqliteJsonDecodeFailures")
        if "AbsoluteWSSendFailBurst" not in alerts:
            errors.append("alerts.yml missing AbsoluteWSSendFailBurst")
        if 'checks["websocket_running"]' not in (
            (ROOT / "api" / "http.py").read_text(encoding="utf-8")
        ):
            errors.append("/health/ready prod must check websocket_running")
        http_py2 = (ROOT / "api" / "http.py").read_text(encoding="utf-8")
        if "lightning_missing" not in http_py2 or "plasma_missing" not in http_py2:
            errors.append("L2 unbound endpoints must surface lightning_missing/plasma_missing")
        if "wasm_missing" not in http_py2:
            errors.append("WASM unbound endpoints must surface wasm_missing")
        if "p2p_missing" not in http_py2:
            errors.append("/network/stats must surface p2p_missing")
        if "proof_ok = bridge_on and oracle_on and rust_path and rpc_on" not in http_py2:
            errors.append("bridge relayer proof_ok must require eth RPC configured")
        if 'raise ValueError("corrupt account storage")' not in http_py2:
            errors.append("eth_getStorageAt must fail on corrupt account storage")
        if "feature_degraded" not in http_py2:
            errors.append("/status must degrade when feature_init_errors present")
        main_py2 = (ROOT / "main.py").read_text(encoding="utf-8")
        if "feature_init_errors" not in main_py2:
            errors.append("main.py must track feature_init_errors on optional module init fail")
        adapter_py = (ROOT / "consensus" / "adapter.py").read_text(encoding="utf-8")
        if "_casper_ingest_fail" not in adapter_py or "casper_ingest_fail" not in adapter_py:
            errors.append("consensus adapter must count casper/beacon ingest failures")
        if '"healthy": ingest_fail == 0' not in adapter_py:
            errors.append("casper/beacon healthy must require zero ingest_fail")
        sync_py = (ROOT / "sync" / "sync_engine.py").read_text(encoding="utf-8")
        if "never leave is_syncing stuck" not in sync_py:
            errors.append("SyncEngine.fast_sync must clear is_syncing in finally")
        if "sync_fail" not in sync_py or "last_sync_error" not in sync_py:
            errors.append("SyncEngine status must expose sync_fail/last_sync_error")
        p2p_py2 = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
        if "chain_compatible" not in p2p_py2 or "transport_healthy" not in p2p_py2:
            errors.append("P2P topology must separate transport_healthy and chain_compatible")
        oracle_py = (ROOT / "features" / "oracle_registry.py").read_text(encoding="utf-8")
        if "oracle signature required" not in oracle_py:
            errors.append("oracle submit_report must require signature when secret set")
        if "One vote per reporter" not in oracle_py:
            errors.append("oracle aggregate must dedupe reporters")
        bridge_py = (ROOT / "bridge" / "abs_bridge.py").read_text(encoding="utf-8")
        if "_rust_decode_fail" not in bridge_py or "get_ops_errors" not in bridge_py:
            errors.append("RustBridge must expose decode/timeout ops error counters")
        mev_py = (ROOT / "features" / "mev_analyzer.py").read_text(encoding="utf-8")
        if "heuristic_signals" not in mev_py:
            errors.append("MEV stats must expose heuristic_signals honesty labels")
        ai_py = (ROOT / "features" / "ai_manager.py").read_text(encoding="utf-8")
        if "model_bound" not in ai_py or "executor_bound" not in ai_py:
            errors.append("AI manager must expose model_bound/executor_bound")
        will_py = (ROOT / "features" / "crypto_will.py").read_text(encoding="utf-8")
        if "create persist failed, refunded" not in will_py:
            errors.append("CryptoWill create must refund on persist failure")
        l1_rpc_py = (ROOT / "bridge" / "l1_rpc.py").read_text(encoding="utf-8")
        if "_receipt_status_ok" not in l1_rpc_py or "status-less" not in l1_rpc_py:
            errors.append("L1 RPC confirmations must require successful receipt status")
        evm_ad = (ROOT / "execution" / "evm_adapter.py").read_text(encoding="utf-8")
        if "_loads_contract_storage" not in evm_ad or "corrupt_storage" not in evm_ad:
            errors.append("EVM adapter must fail-closed on corrupt contract storage")
        if "static_create_rejected" not in evm_ad or "read_only=True" not in evm_ad:
            errors.append("EVM static_call must reject nested CREATE and use read_only")
        if "force will execute forbidden in prod" not in http_py2:
            errors.append("/will/execute must reject force in prod")
        if '"execution_bound": False' not in http_py2 or "in_memory_registry" not in http_py2:
            errors.append("multisig list must expose execution_bound/persistent honesty")
        nft_py = (ROOT / "features" / "nft.py").read_text(encoding="utf-8")
        if "on_chain_standard" not in nft_py or "execution_bound" not in nft_py:
            errors.append("NFT get_stats must expose execution_bound honesty labels")
        if "feature_nft" not in main_py2 or "NFT Marketplace: disabled" not in main_py2:
            errors.append("main.py must gate NFT on feature_nft")
        pq_py = (ROOT / "features" / "postquantum.py").read_text(encoding="utf-8")
        if "educational_only" not in pq_py or "nist_ml_dsa" not in pq_py:
            errors.append("PQ get_stats must expose educational capability matrix")
        if "FEATURE_NFT" not in (ROOT / "runtime" / "config.py").read_text(encoding="utf-8"):
            errors.append("config must include FEATURE_NFT prod block")
        if "force plasma finalize forbidden in prod" not in http_py2:
            errors.append("/plasma/finalize-exit must reject force in prod")
        if "claim_and_credit_bridge_event" not in (
            ROOT / "storage" / "database.py"
        ).read_text(encoding="utf-8"):
            errors.append("SQLite must provide claim_and_credit_bridge_event")
        bridge_py2 = (ROOT / "bridge" / "abs_bridge.py").read_text(encoding="utf-8")
        if "l1_event_bound" not in bridge_py2 or "replay_key" not in bridge_py2:
            errors.append("RustBridge stats must expose l1_event_bound / replay_key honesty")
        if "from_chain:event_tx_hash:log_index" not in bridge_py2:
            errors.append("bridge confirm_incoming must use event-derived replay key")
        if "debit_and_create_bridge_lock" not in bridge_py2:
            errors.append("lock_and_bridge must use debit_and_create_bridge_lock")
        if '"to_chain": self._normalize_chain(lock.get("to_chain", ""))' not in bridge_py2:
            errors.append("confirm_lock must pass lock to_chain to Rust L1 verify")
        if "BRIDGE_REQUIRE_L1_EVENT" not in bridge_py2 or "BRIDGE_L1_LOCK_CONTRACT" not in bridge_py2:
            errors.append("Rust subprocess env must forward L1 event binding settings")
        rust_main = (ROOT / "bridge" / "rust_bridge" / "src" / "main.rs").read_text(encoding="utf-8")
        if "receipt_status_ok" not in rust_main:
            errors.append("Rust bridge must require successful receipt status")
        if '"lock" | "bridge"' not in rust_main:
            errors.append("Rust bridge must verify L1 for lock/bridge commands")
        if "BRIDGE_REQUIRE_L1_EVENT" not in rust_main or "receipt_has_contract_log" not in rust_main:
            errors.append("Rust bridge must support BRIDGE_REQUIRE_L1_EVENT contract log binding")
        if "feature_smart_accounts" not in main_py2:
            errors.append("main.py must gate Smart Accounts on feature_smart_accounts")
        sa_py = (ROOT / "features" / "smart_accounts.py").read_text(encoding="utf-8")
        if "execution_bound" not in sa_py or "in_memory_registry" not in sa_py:
            errors.append("SmartAccountManager stats must expose execution_bound honesty")
        if "feature_minivm" not in main_py2 or "MiniVM: disabled" not in main_py2:
            errors.append("main.py must gate MiniVM on feature_minivm")
        if "unsigned DAO vote forbidden in prod" not in http_py2:
            errors.append("/pools/dao/vote must reject unsigned votes in prod")
        if "multi-hop lightning routing not implemented" not in http_py2:
            errors.append("/lightning/route must reject multi-hop until implemented")
        if "private keys in query forbidden" not in http_py2:
            errors.append("GET /zk/transaction must forbid private keys in query")
        if "zk_missing" not in http_py2:
            errors.append("ZK prove/range must not invent arithmetic validity when ZK missing")
        ln_py = (ROOT / "features" / "lightning.py").read_text(encoding="utf-8")
        if '"routing_enabled": False' not in ln_py or "direct_channel_only" not in ln_py:
            errors.append("Lightning stats must not claim multi-hop routing_enabled")
        if "FEATURE_MINIVM" not in (ROOT / "runtime" / "config.py").read_text(encoding="utf-8"):
            errors.append("config must include FEATURE_MINIVM prod block")
        if "heuristic_low_risk" not in (
            ROOT / "features" / "reorg_predictor.py"
        ).read_text(encoding="utf-8"):
            errors.append("reorg predictor must not emit reserved finalized heuristic label")
        if 'return "finalized"' in (
            ROOT / "features" / "reorg_predictor.py"
        ).read_text(encoding="utf-8"):
            errors.append("reorg predictor still returns finalized confidence label")
        if "standalone_observer" not in http_py2:
            errors.append("/finality/stats must label standalone_observer")
        if "finality_engine_standalone_observer" not in http_py2:
            errors.append("/status must expose finality_engine_standalone_observer")
        if "wasm_operational" not in http_py2:
            errors.append("/status must expose wasm_operational separately from wasm registry")
        wasm_py = (ROOT / "features" / "wasm_vm.py").read_text(encoding="utf-8")
        if "wasmtime_available" not in wasm_py or "pseudo_token_host" not in wasm_py:
            errors.append("WASM get_stats must expose wasmtime_available / pseudo_token_host")
        if "Binary WASM requires wasmtime" not in wasm_py:
            errors.append("WASM deploy must reject binary modules without wasmtime")
        if "deterministic_hash_selection" not in main_py2:
            errors.append("main.py must not greenwash ValidatorSelection as RANDAO")
        if "FEATURE_VALIDATOR_SELECTION" not in (
            ROOT / "runtime" / "config.py"
        ).read_text(encoding="utf-8"):
            errors.append("config must include FEATURE_VALIDATOR_SELECTION")
        chain_st = (ROOT / "storage" / "chain_storage.py").read_text(encoding="utf-8")
        if "abs_chain_replace_" not in chain_st or "os.rename(tmp_blocks" not in chain_st:
            errors.append("ChainStorage.replace_chain must atomically swap temp blocks dir")
        # v1.3.37 — bridge L1 proof / blind confirm / light / PBS / AI honesty
        cfg_py = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
        if "env cannot weaken L1 proof requirement" not in cfg_py:
            errors.append("prod config must forbid BRIDGE_REQUIRE_L1_PROOF=false via env")
        if "FEATURE_AI_VALIDATOR" not in cfg_py:
            errors.append("config must include FEATURE_AI_VALIDATOR")
        relayer_py = (ROOT / "scripts" / "bridge_relayer.py").read_text(encoding="utf-8")
        if "refusing --allow-blind-confirm against prod API" not in relayer_py:
            errors.append("bridge_relayer must hard-fail --allow-blind-confirm on prod API")
        light_py = (ROOT / "light" / "light_client.py").read_text(encoding="utf-8")
        if "require_trusted_anchor" not in light_py or "trusted_local_replay" not in light_py:
            errors.append("light client must reject unanchored peer bootstrap")
        if "peer_import_requires_trusted_anchor" not in light_py:
            errors.append("light get_stats must expose peer_import_requires_trusted_anchor")
        pbs_py = (ROOT / "consensus" / "pbs.py").read_text(encoding="utf-8")
        if '"mev_protection": False' not in pbs_py or '"ordering_applied": False' not in pbs_py:
            errors.append("PBS must label mev_protection/ordering_applied false")
        if "PBS auction (MEV protection)" in main_py2 or "PBS handles protection" in main_py2:
            errors.append("main.py must not claim PBS MEV protection")
        if "feature_ai_validator" not in main_py2:
            errors.append("main.py must gate AIValidatorEngine on feature_ai_validator")
        ai_py = (ROOT / "features" / "ai_validator.py").read_text(encoding="utf-8")
        if "invented_numbers" not in ai_py or "consensus_wired" not in ai_py:
            errors.append("AI validator must expose simulation honesty (no invented MEV numbers)")
        if "random.uniform" in ai_py and "detect_mev_opportunity" in ai_py:
            # Fail if invented MEV numbers remain inside detect_mev_opportunity body.
            start = ai_py.find("def detect_mev_opportunity")
            end = ai_py.find("\n    def ", start + 1)
            body = ai_py[start:end] if start >= 0 else ai_py
            if "random.uniform" in body:
                errors.append("AI validator must not invent MEV profit/probability via random.uniform")
        if "consensus_wired" not in http_py2 or "model_bound" not in http_py2:
            errors.append("/ai/* API must expose consensus_wired / model_bound honesty")
        # v1.3.38 — native GHOST + simple block apply/replay
        ghost_py = (ROOT / "consensus" / "ghost.py").read_text(encoding="utf-8")
        if "ghost_select_head" not in ghost_py or "ghost_cumulative_weight" not in ghost_py:
            errors.append("ghost.py must route fork-choice to abs_native kernels")
        if "blockchain_apply_simple_block" not in main_py2 and "blockchain_apply_simple_block" not in (
            ROOT / "core" / "blockchain.py"
        ).read_text(encoding="utf-8"):
            errors.append("blockchain.py must wire blockchain_apply_simple_block")
        bc_py = (ROOT / "core" / "blockchain.py").read_text(encoding="utf-8")
        if "_apply_simple_block_native" not in bc_py or "_replay_simple_range_native" not in bc_py:
            errors.append("blockchain must expose native simple apply/replay helpers")
        if "blockchain_replay_simple_blocks" not in bc_py:
            errors.append("blockchain reorg must prefer blockchain_replay_simple_blocks")
        native_py = (ROOT / "crypto" / "native.py").read_text(encoding="utf-8")
        for sym in (
            "ghost_select_head",
            "blockchain_apply_simple_block",
            "blockchain_replay_simple_blocks",
            "lmd_compute_weights",
        ):
            if f"def {sym}" not in native_py:
                errors.append(f"crypto/native.py must export {sym}")
        # v1.3.39 — FFG finality + slashing conflict kernels
        for sym in (
            "ffg_evaluate_epoch",
            "ffg_threshold",
            "slash_check_double_vote",
            "slash_check_double_proposal",
            "fe_quorum_reached",
            "fe_can_finalize",
        ):
            if f"def {sym}" not in native_py:
                errors.append(f"crypto/native.py must export {sym} (v1.3.39)")
        if "ffg_evaluate_epoch" not in (
            ROOT / "consensus" / "finality_casper.py"
        ).read_text(encoding="utf-8"):
            errors.append("finality_casper.py must route to ffg_evaluate_epoch")
        if "slash_check_double_vote" not in (
            ROOT / "consensus" / "slashing.py"
        ).read_text(encoding="utf-8"):
            errors.append("slashing.py must route to slash_check_double_vote")
        if "fe_quorum_reached" not in (
            ROOT / "finality_engine.py"
        ).read_text(encoding="utf-8"):
            errors.append("finality_engine.py must route to fe_quorum_reached")
        ffg_rs = ROOT / "native" / "abs_native" / "src" / "consensus_ffg.rs"
        if not ffg_rs.is_file():
            errors.append("native consensus_ffg.rs missing")
        # v1.3.40 — eth raw tx decode kernel
        for sym in ("decode_eth_raw_tx", "decode_eth_raw_tx_hex"):
            if f"def {sym}" not in native_py:
                errors.append(f"crypto/native.py must export {sym} (v1.3.40)")
        eth_tx_py = (ROOT / "crypto" / "eth_tx.py").read_text(encoding="utf-8")
        if "decode_eth_raw_tx" not in eth_tx_py:
            errors.append("eth_tx.py must prefer decode_eth_raw_tx native path")
        eth_tx_rs = ROOT / "native" / "abs_native" / "src" / "eth_tx.rs"
        if not eth_tx_rs.is_file():
            errors.append("native eth_tx.rs missing")
    except Exception as exc:
        errors.append(f"fail-loud v1.3.28..40 honesty inspect failed: {exc}")
    try:
        metrics_py = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
        if "abs_sync_wire_probe_probed" not in metrics_py:
            errors.append("metrics.py must export abs_sync_wire_probe_probed")
        if "-1=never probed" not in metrics_py and "never probed" not in metrics_py.lower():
            errors.append("metrics.py must document abs_sync_wire_probe_ok=-1 as never-probed")
        if "return -1" not in metrics_py:
            errors.append("metrics.py must emit abs_sync_wire_probe_ok=-1 when never probed")
        alerts = (ROOT / "deploy" / "prometheus" / "alerts.yml").read_text(encoding="utf-8")
        if "AbsoluteSyncWireProbeNeverProbed" not in alerts:
            errors.append("alerts.yml missing AbsoluteSyncWireProbeNeverProbed")
        if "AbsoluteProdSqliteEngine" not in alerts:
            errors.append("alerts.yml missing AbsoluteProdSqliteEngine")
    except Exception as exc:
        errors.append(f"fail-loud metrics/alerts inspect failed: {exc}")
    try:
        from core.blockchain import Blockchain

        gen_src = inspect.getsource(Blockchain._ensure_genesis)
        if "genesis meta write failed" not in gen_src:
            errors.append("Blockchain._ensure_genesis must log genesis meta failures")
        if "except Exception:\n                pass" in gen_src and "set_meta" in gen_src:
            # still allow other passes elsewhere in function; only fail if set_meta still bare-pass
            if "except Exception:\n                pass\n            try:\n                self.db.set_meta" in gen_src:
                errors.append("Blockchain._ensure_genesis still silent-passes tokenomics meta")
        add_src = inspect.getsource(Blockchain.add_block)
        if "record_state_root_mismatch failed" not in add_src:
            errors.append("Blockchain.add_block must log mismatch audit failures")
    except Exception as exc:
        errors.append(f"fail-loud blockchain inspect failed: {exc}")
    try:
        http_py = (ROOT / "api" / "http.py").read_text(encoding="utf-8")
        if "peer_probe_error" not in http_py:
            errors.append("GET /chain/state-root/status must expose peer_probe_error")
        if "peer_probe_error" not in http_py or "state consistency harness peer probe failed" not in http_py:
            errors.append("state consistency harness must expose/log peer_probe_error")
        if "prices_error" not in http_py:
            errors.append("/oracles/all must expose prices_error on failure")
        if "repair_error" not in http_py:
            errors.append("POST /chain/consistency/repair must expose repair_error")
        if "Never greenwash consistency from harness alone" not in http_py:
            errors.append("POST /chain/consistency/repair must require sync_state (not harness alone)")
        if "Do not claim fully synced while tip state is inconsistent" not in http_py:
            errors.append("eth_syncing must stay syncing when peers + inconsistent state")
        if "never wire-probed" not in http_py:
            errors.append(
                "eth_syncing must stay syncing when peers + wire probe never ran"
            )
        if 'db_engine == "rocksdb"' not in http_py:
            errors.append("/metrics must not apply Rocks config_fallback on non-rocks engines")
        if "peer_probe_ok" not in http_py:
            errors.append("state consistency harness must include peer_probe_ok check")
        if "state_root_encoding_honest" not in http_py:
            errors.append("state consistency harness must include state_root_encoding_honest check")
        if "/chain/state-root/encoding" not in http_py:
            errors.append("GET /chain/state-root/encoding missing")
        if "Invalid block number:" not in http_py:
            errors.append("block URL handlers must fail-loud on invalid block number")
        if "module_probes" not in http_py:
            errors.append("GET /features must expose module_probes for wasm/plasma")
        feat_init = (ROOT / "features" / "__init__.py").read_text(encoding="utf-8")
        for name in ("lightning", "zk", "ai_agents", "mev", "pq"):
            if f'"{name}"' not in feat_init:
                errors.append(f"OPTIONAL_MODULE_PROBES must include {name}")
    except Exception as exc:
        errors.append(f"fail-loud http inspect failed: {exc}")
    return errors, warnings


def _check_audit_pack_export() -> tuple[list[str], list[str]]:
    """Audit/CI pack must snapshot encoding contract and Rust hardening checks."""
    errors: list[str] = []
    warnings: list[str] = []
    try:
        ap = (ROOT / "scripts" / "export_audit_pack.py").read_text(encoding="utf-8")
        for needle in ("state_root_encoding.json", "state_root_encoding_status"):
            if needle not in ap:
                errors.append(f"export_audit_pack must include {needle}")
        main_py = (ROOT / "main.py").read_text(encoding="utf-8")
        if "genesis_founder meta read failed" not in main_py:
            errors.append("main.py must fail-loud on genesis_founder meta read")
        if "devnet manifest resolve failed" not in main_py:
            errors.append("main.py must fail-loud on devnet manifest resolve")
        stamp = (ROOT / "scripts" / "stamp_release_evidence.py").read_text(encoding="utf-8")
        if "require-soak-hours" not in stamp:
            errors.append("stamp_release_evidence must support --require-soak-hours")
        test_ci = (ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")
        for needle in (
            "Rust format check (abs_native + rust_bridge)",
            "cargo clippy --manifest-path native/abs_native/Cargo.toml",
            "cargo clippy --manifest-path bridge/rust_bridge/Cargo.toml",
        ):
            if needle not in test_ci:
                errors.append(f"test.yml missing Rust hardening step: {needle}")
        sec_ci = (ROOT / ".github" / "workflows" / "security-audit.yml").read_text(encoding="utf-8")
        for needle in (
            "Dependency audit (cargo-audit)",
            "cargo audit --file native/abs_native/Cargo.lock",
            "cargo audit --file bridge/rust_bridge/Cargo.lock",
        ):
            if needle not in sec_ci:
                errors.append(f"security-audit.yml missing Rust audit step: {needle}")
        native_lib = (ROOT / "native" / "abs_native" / "src" / "lib.rs").read_text(encoding="utf-8")
        consensus_src = (
            ROOT / "native" / "abs_native" / "src" / "consensus_select.rs"
        ).read_text(encoding="utf-8")
        p2p_wire_src = (
            ROOT / "native" / "abs_native" / "src" / "p2p_wire.rs"
        ).read_text(encoding="utf-8")
        amount_src = (
            ROOT / "native" / "abs_native" / "src" / "amount.rs"
        ).read_text(encoding="utf-8")
        storage_src = (
            ROOT / "native" / "abs_native" / "src" / "storage" / "mod.rs"
        ).read_text(encoding="utf-8")
        native_surface = (
            native_lib
            + "\n"
            + consensus_src
            + "\n"
            + p2p_wire_src
            + "\n"
            + amount_src
            + "\n"
            + storage_src
        )
        for needle in (
            "MAX_IMPORTED_BLOCKS",
            "MAX_PEER_HEADERS",
            "MAX_BLOCK_JSON_BYTES",
            "MAX_ACCOUNTS_JSON_BYTES",
            "MAX_STATE_ROOT_ACCOUNTS",
            "MAX_STATE_ROOT_BLOBS",
            "MAX_ACCOUNT_BLOB_BYTES",
            "too_many_blocks",
            "too_many_headers",
            "block_json_too_large",
            "too_many_account_blobs",
            "column_families",
            "rocksdb_missing_column_family",
            "account_blob_too_large",
            "MAX_CONSENSUS_VALIDATORS",
            "too_many_validators",
            "consensus_stake_weighted_proposer",
            "state_engine_root_from_accounts_json",
            "parse_p2p_wire_line",
            "encode_p2p_wire_message",
            "p2p_line_too_large",
            "verify_attestation_secp256k1",
            "hash_sorted_json",
            "amount_to_satoshi",
            "amount_apply_delta_satoshi",
            "state_engine_apply_transactions",
            "too_many_txs",
            "plan_transfer_fees",
            "can_afford_transfer",
            "validate_p2p_status_payload",
            "validate_p2p_attestation_payload",
            "validate_p2p_block_announce",
            "validate_p2p_state_root_request",
            "validate_p2p_state_root_response",
            "validate_p2p_handshake_payload",
            "validate_p2p_get_blocks_payload",
            "validate_p2p_wire_tx",
            "validate_p2p_mempool_batch",
            "validate_p2p_validator_register",
            "validate_p2p_peers_list",
            "validate_p2p_get_block",
            "validate_p2p_get_block_by_hash",
            "validate_p2p_blocks_batch",
            "validate_p2p_cross_shard_tx",
            "validate_p2p_cross_shard_ack",
            "validate_p2p_shard_migration",
        ):
            if needle not in native_surface:
                errors.append(f"abs_native lib missing fail-closed bound: {needle}")
    except Exception as exc:
        errors.append(f"audit pack export inspect failed: {exc}")
    return errors, warnings


def _check_balance_precision() -> tuple[list[str], list[str]]:
    """Satoshi dual-write surface for industrial money path."""
    errors: list[str] = []
    warnings: list[str] = []
    try:
        from runtime.amount import (
            SATOSHI_MULTIPLIER,
            apply_delta_satoshi,
            dual_write_balance,
            to_satoshi,
        )
    except ImportError as exc:
        errors.append(f"runtime.amount import failed: {exc}")
        return errors, warnings
    if SATOSHI_MULTIPLIER != 1_000_000:
        errors.append(f"SATOSHI_MULTIPLIER unexpected: {SATOSHI_MULTIPLIER}")
    if to_satoshi(1) != 1_000_000:
        errors.append("to_satoshi(1) != 1_000_000")
    row: dict = {}
    dual_write_balance(row, "1.5")
    if row.get("balance_satoshi") != 1_500_000:
        errors.append("dual_write_balance failed for 1.5 ABS")
    if apply_delta_satoshi(1_000_000, -0.5) != 500_000:
        errors.append("apply_delta_satoshi failed")
    from storage.database import Database

    if not hasattr(Database, "get_balance_satoshi"):
        errors.append("Database missing get_balance_satoshi")
    try:
        from storage.rocks_store import RocksChainStore

        if not hasattr(RocksChainStore, "get_balance_satoshi"):
            errors.append("RocksChainStore missing get_balance_satoshi")
        else:
            import inspect

            # Fail-closed: industrial wheel must expose CF opt-in surface.
            try:
                import abs_native as _abs

                if hasattr(_abs, "RocksEngine"):
                    sig = inspect.signature(_abs.RocksEngine)
                    if "column_families" not in sig.parameters:
                        errors.append("RocksEngine missing column_families kwarg")
            except ImportError:
                pass
    except ImportError as exc:
        warnings.append(f"RocksChainStore unavailable (optional for this host): {exc}")
    try:
        from runtime.state_truth import canonical_balance_satoshi
        from execution.state_engine import StateEngine

        eng = StateEngine()
        eng.create_genesis({"x": 1})
        if eng.get_balance_satoshi("x") != 1_000_000:
            errors.append("StateEngine create_genesis not storing satoshi")
        if canonical_balance_satoshi(None, "x") != 0:
            errors.append("canonical_balance_satoshi(None) should be 0")
        from blockchain.state_adapter import DatabaseStateAdapter
        from storage.database import Database as _DbCheck
        import tempfile, os

        _p = os.path.join(tempfile.mkdtemp(), "gate.db")
        _d = _DbCheck(_p)
        _d.initialize()
        _d.reset_accounts_from_alloc({"gate": 2})
        if _d.get_balance_satoshi("gate") != 2_000_000:
            errors.append("reset_accounts_from_alloc missing balance_satoshi")
        if DatabaseStateAdapter(_d).get_balance_satoshi("gate") != 2_000_000:
            errors.append("DatabaseStateAdapter not using satoshi path")
        # Tip state-root soak contract: float "b" must remain (do not silently switch to satoshi)
        from crypto.native import _python_state_root_from_accounts
        import inspect

        src = inspect.getsource(_python_state_root_from_accounts)
        if '"b"' not in src or "round(float" not in src:
            errors.append("tip state_root Python path no longer uses float round(balance,12) — soak contract broken")
        from blockchain.immutable_state import ImmutableStateManager

        if not hasattr(ImmutableStateManager, "reconcile_from_store"):
            errors.append("ImmutableStateManager missing reconcile_from_store")
        ims = ImmutableStateManager()
        ims.reconcile_from_store(_d, ["gate"])
        if ims.get_balance_satoshi("gate") != 2_000_000:
            errors.append("IMS reconcile_from_store did not mirror DB satoshi")
        # get_address_activity prefers satoshi
        act = _d.get_address_activity("gate")
        if int(act.get("balance_satoshi", -1)) != 2_000_000:
            errors.append("get_address_activity missing balance_satoshi")
    except Exception as exc:
        errors.append(f"state_truth/StateEngine check failed: {exc}")
    return errors, warnings


def _check_native_wheel() -> tuple[list[str], list[str]]:
    """Require abs_native self-test and prod-critical exports when wheel is present."""
    errors: list[str] = []
    warnings: list[str] = []
    from crypto import native

    status = native.native_crypto_status(required=True)
    if not status.get("available"):
        errors.append(f"abs_native unavailable: {status.get('error') or 'import failed'}")
        return errors, warnings
    if not status.get("self_test"):
        errors.append("abs_native self_test failed")
    try:
        import abs_native as _abs

        for sym in (
            "RocksEngine",
            "evm_run_until_halt",
            "validate_imported_block_chain",
            "consensus_stake_weighted_proposer",
            "state_engine_root_from_accounts_json",
            "parse_p2p_wire_line",
            "verify_attestation_secp256k1",
            "amount_to_satoshi",
            "state_engine_apply_transactions",
            "plan_transfer_fees",
            "can_afford_transfer",
            "validate_p2p_status_payload",
            "validate_p2p_attestation_payload",
            "validate_p2p_block_announce",
            "validate_p2p_state_root_request",
            "validate_p2p_state_root_response",
            "validate_p2p_handshake_payload",
            "validate_p2p_get_blocks_payload",
            "validate_p2p_wire_tx",
            "validate_p2p_mempool_batch",
            "validate_p2p_validator_register",
            "validate_p2p_peers_list",
            "validate_p2p_get_block",
            "validate_p2p_get_block_by_hash",
            "validate_p2p_blocks_batch",
            "validate_p2p_cross_shard_tx",
            "validate_p2p_cross_shard_ack",
            "validate_p2p_shard_migration",
            "pubkey_to_eth_address",
            "rlp_encode",
            "rlp_decode_single",
        ):
            if not hasattr(_abs, sym):
                errors.append(f"abs_native missing export: {sym}")
    except ImportError as exc:
        errors.append(f"abs_native import failed: {exc}")
    return errors, warnings


def _check_rust_bridge_binary() -> tuple[list[str], list[str]]:
    """Smoke-test abs_bridge_bin when present; require if any live prod JSON enables bridge."""
    errors: list[str] = []
    warnings: list[str] = []
    from runtime.config import Config

    bridge_required = False
    for rel in (
        "docker/node.prod.mesh1.json",
        "docker/node.prod.mesh2.json",
        "docker/node.prod.mesh3.json",
        "docker/node.prod.json",
        "deploy/k8s/node.prod.k8s.json",
        "node.prod.example.json",
        "node.prod.mainnet-v1.example.json",
    ):
        path = ROOT / rel
        if not path.is_file():
            continue
        try:
            cfg_json = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if cfg_json.get("bridge_enabled") is True:
            bridge_required = True
            break

    cfg = Config()
    path = cfg.resolve_rust_bridge_path()
    if not path or not __import__("os").path.isfile(path):
        msg = f"abs_bridge_bin missing: {path or '(unset)'}"
        if bridge_required:
            errors.append(msg + " (required while prod JSON has bridge_enabled=true)")
        else:
            warnings.append(msg + " (OK while bridge OFF)")
        return errors, warnings
    from bridge.health import check_rust_bridge_binary

    result = check_rust_bridge_binary(path)
    if not result.get("ok"):
        errors.append(f"abs_bridge_bin smoke failed: {result.get('error')}")
    return errors, warnings


def run_industrial_gate(
    *,
    prod_smoke_spawn: bool = False,
    min_soak_hours: float = 0,
    ceremony_dir: str = "",
    require_ceremony_pin: bool = False,
    strict_audit: bool = False,
    bridge_cutover: bool = False,
    live_prod_mesh: bool = False,
    probe_l1: bool = False,
    probe_l1_rpc_only: bool = False,
    bridge_live: bool = False,
    fail_on_warnings: bool = False,
) -> int:
    import importlib.util

    native_errors, native_warnings = _check_native_wheel()
    bridge_errors, bridge_warnings = _check_rust_bridge_binary()
    p2p_errors, p2p_warnings = _check_p2p_hardening()
    balance_errors, balance_warnings = _check_balance_precision()
    fail_loud_errors, fail_loud_warnings = _check_fail_loud_surfaces()
    audit_pack_errors, audit_pack_warnings = _check_audit_pack_export()
    soak_errors: list[str] = []
    ceremony_errors: list[str] = []
    ceremony_warnings: list[str] = []

    if ceremony_dir:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "ceremony_preflight", ROOT / "scripts" / "ceremony_preflight.py"
        )
        cp = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(cp)
        ceremony_errors, ceremony_warnings, _meta = cp.run_ceremony_preflight(
            ceremony_dir,
            require_env_pin=require_ceremony_pin,
        )

    if min_soak_hours > 0:
        soak_candidates = [
            ROOT / "logs" / "soak_report_48h.json",
            ROOT / "logs" / "soak_report.json",
        ]
        soak_path = next((p for p in soak_candidates if p.is_file()), soak_candidates[0])
        if not soak_path.is_file():
            soak_errors.append(
                f"soak_report missing: {soak_path} (need {min_soak_hours}h prod soak)"
            )
        else:
            try:
                soak = json.loads(soak_path.read_text(encoding="utf-8"))
                hrs = float(soak.get("hours_requested", 0) or 0)
                if hrs < min_soak_hours:
                    soak_errors.append(f"soak_report hours_requested={hrs} < {min_soak_hours}")
                elapsed = soak.get("hours_elapsed")
                if elapsed is None:
                    try:
                        started = datetime.fromisoformat(
                            str(soak.get("started_at", "")).replace("Z", "+00:00")
                        )
                        ended = datetime.fromisoformat(
                            str(soak.get("ended_at", "")).replace("Z", "+00:00")
                        )
                        elapsed = (ended - started).total_seconds() / 3600.0
                    except (TypeError, ValueError, OSError):
                        elapsed = None
                if elapsed is not None and float(elapsed) < float(min_soak_hours) * 0.95:
                    soak_errors.append(
                        f"soak_report hours_elapsed={float(elapsed):.2f} < "
                        f"{min_soak_hours}*0.95 (wall-clock duration short)"
                    )
                if not soak.get("passed"):
                    soak_errors.append(f"soak_report passed=false (see {soak_path})")
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                soak_errors.append(f"soak_report unreadable: {exc}")

    spec = importlib.util.spec_from_file_location(
        "mainnet_readiness", ROOT / "scripts" / "mainnet_readiness.py"
    )
    mr = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mr)

    errors, warnings, sections = mr.run_gate(
        live=False,
        live_prod_mesh=live_prod_mesh,
        strict_audit=strict_audit,
        ceremony_dir=ceremony_dir,
        bridge_cutover=bridge_cutover,
        probe_l1=probe_l1,
        probe_l1_rpc_only=probe_l1_rpc_only,
        bridge_live=bridge_live,
    )
    errors.extend(soak_errors)
    errors.extend(native_errors)
    errors.extend(bridge_errors)
    errors.extend(p2p_errors)
    errors.extend(balance_errors)
    errors.extend(fail_loud_errors)
    errors.extend(audit_pack_errors)
    errors.extend(ceremony_errors)
    warnings.extend(native_warnings)
    warnings.extend(bridge_warnings)
    warnings.extend(p2p_warnings)
    warnings.extend(balance_warnings)
    warnings.extend(fail_loud_warnings)
    warnings.extend(audit_pack_warnings)
    warnings.extend(ceremony_warnings)
    report = {
        "ok": not errors,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "errors": errors,
        "warnings": warnings,
        "sections": sections,
        "native_wheel": not native_errors,
        "p2p_hardening": not p2p_errors,
        "balance_precision": not balance_errors,
        "fail_loud_surfaces": not fail_loud_errors,
    }

    if prod_smoke_spawn:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "verify_p2p_ci", ROOT / "scripts" / "verify_p2p_ci.py"
        )
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        rc = mod.run_prod_smoke_spawn()
        report["prod_smoke_spawn_rc"] = rc
        if rc != 0:
            errors.append(f"prod_smoke_spawn exited {rc}")

    for label, (script, attr) in (
        ("runbook", ("runbook_check.py", "main")),
        ("evm_opcode_parity", ("evm_opcode_parity_gate.py", "main")),
        ("prod_gate", ("prod_gate.py", "main")),
        ("bridge_off_audit", ("bridge_off_audit_gate.py", "main")),
    ):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            label, ROOT / "scripts" / script
        )
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        rc = int(getattr(mod, attr)())
        report[f"{label}_rc"] = rc
        if rc != 0:
            errors.append(f"{label} gate exited {rc}")

    out = ROOT / "data" / "industrial_gate.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    report["ok"] = not errors
    report["errors"] = errors
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if errors:
        print("FAIL: industrial gate")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("OK: industrial gate")
    if warnings:
        print(f"  ({len(warnings)} warning(s) — see {out})")
        for w in warnings[:12]:
            print(f"  warn: {w}")
        if len(warnings) > 12:
            print(f"  warn: ... +{len(warnings) - 12} more")
        if fail_on_warnings:
            print("FAIL: industrial gate (--fail-on-warnings)")
            return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Industrial code gate (no strict audit)")
    parser.add_argument(
        "--prod-smoke-spawn",
        action="store_true",
        help="Run isolated verify_p2p_ci --mode prod-smoke after static checks",
    )
    parser.add_argument(
        "--min-soak-hours",
        type=float,
        default=0,
        help="Require logs/soak_report.json with passed=true and hours_requested >= N (0=skip)",
    )
    parser.add_argument(
        "--ceremony-dir",
        default="",
        help="Run ceremony_preflight on this dir before static checks (empty=skip)",
    )
    parser.add_argument(
        "--require-ceremony-pin",
        action="store_true",
        help="With --ceremony-dir, require GENESIS_CEREMONY_HASH to match",
    )
    parser.add_argument("--json", action="store_true", help="Print report path only")
    parser.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="Exit non-zero when warnings are present (release strict mode)",
    )
    parser.add_argument(
        "--bridge-cutover",
        action="store_true",
        help="Include bridge L1 cutover static gate",
    )
    parser.add_argument(
        "--probe-l1",
        action="store_true",
        help="With --bridge-cutover, probe L1 RPC and contract bytecode",
    )
    parser.add_argument(
        "--probe-l1-rpc-only",
        action="store_true",
        help="With --bridge-cutover, probe ETH_RPC_URL only",
    )
    parser.add_argument(
        "--bridge-live",
        action="store_true",
        help="With --bridge-cutover, live checks on bridge-enabled prod node",
    )
    args = parser.parse_args()
    rc = run_industrial_gate(
        prod_smoke_spawn=args.prod_smoke_spawn,
        min_soak_hours=args.min_soak_hours,
        ceremony_dir=args.ceremony_dir,
        require_ceremony_pin=args.require_ceremony_pin,
        bridge_cutover=args.bridge_cutover,
        probe_l1=args.probe_l1,
        probe_l1_rpc_only=args.probe_l1_rpc_only,
        bridge_live=args.bridge_live,
        fail_on_warnings=args.fail_on_warnings,
    )
    if args.json:
        print(str(ROOT / "data" / "industrial_gate.json"))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
