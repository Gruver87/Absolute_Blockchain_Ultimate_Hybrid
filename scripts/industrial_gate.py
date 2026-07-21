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
        "abs_rocksdb_column_families",
    ):
        if needle not in metrics_src:
            errors.append(f"metrics.py missing Prometheus series: {needle}")
    alerts_src = (ROOT / "deploy" / "prometheus" / "alerts.yml").read_text(encoding="utf-8")
    for needle in (
        "abs_p2p_shape_rejects_total",
        "abs_p2p_rate_limit_drops_total",
        "abs_p2p_peer_send_fail_total",
        "abs_p2p_handshake_rejects_total",
        "abs_p2p_ops_errors",
        "abs_rocksdb_block_cache_mb",
    ):
        if needle not in alerts_src:
            errors.append(f"prometheus alerts.yml missing rule surface: {needle}")
    dash_src = (ROOT / "deploy" / "grafana" / "dashboard.json").read_text(encoding="utf-8")
    for needle in (
        "abs_p2p_peer_send_fail_total",
        "abs_p2p_ops_errors",
        "mid_session_handshake",
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
        "rocksdb_sync",
        "rocksdb_block_cache_mb",
        "rocksdb_write_buffer_mb",
        "rocksdb_column_families",
        "bridge_enabled",
        "require_native_crypto",
    )
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
    try:
        from sync.sync_engine import SyncEngine

        src = inspect.getsource(SyncEngine.sync_state)
        if "peer state_root wire probe failed" not in src:
            errors.append("SyncEngine.sync_state must log wire probe failures")
        status_src = inspect.getsource(SyncEngine.get_status)
        if "wire_probe_ok" not in status_src:
            errors.append("SyncEngine.get_status missing wire_probe_ok")
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
        if "self.p2p._state_consistent = False" not in main_py:
            errors.append("main.py must clear _state_consistent on sync probe failure")
        for needle in (
            "[Mining] PBS auction failed",
            "[Mining] cross-shard processing failed",
            "[Mining] epoch pool unlock failed",
        ):
            if needle not in main_py:
                errors.append(f"main.py mining loop must log: {needle}")
    except Exception as exc:
        errors.append(f"fail-loud main.py inspect failed: {exc}")
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
    """Smoke-test abs_bridge_bin when present (optional warning if missing)."""
    errors: list[str] = []
    warnings: list[str] = []
    from runtime.config import Config

    cfg = Config()
    path = cfg.resolve_rust_bridge_path()
    if not path or not __import__("os").path.isfile(path):
        warnings.append(f"abs_bridge_bin missing: {path or '(unset)'}")
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
