#!/usr/bin/env python3
"""Live production stack smoke checks (HTTP endpoints)."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Tuple

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.mainnet_constants import MAINNET_V1_CHAIN_ID


def _fetch(url: str, timeout: float = 8.0) -> Tuple[int, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode()
        try:
            return resp.status, json.loads(raw)
        except json.JSONDecodeError:
            return resp.status, raw


def run_prod_smoke(base: str = "http://127.0.0.1:8080") -> Dict[str, Any]:
    """Return {ok, errors, checks} for a running prod node."""
    base = base.rstrip("/")
    errors: List[str] = []
    checks: Dict[str, bool] = {}
    bridge_enabled = True

    try:
        status, node_status = _fetch(f"{base}/status")
        checks["status_http"] = status == 200
        mode = node_status.get("deployment_mode")
        checks["deployment_mode_prod"] = mode == "prod"
        bridge_enabled = bool(node_status.get("bridge_enabled", True))
        if mode != "prod":
            errors.append(f"/status deployment_mode={mode!r}, expected prod")
        if not node_status.get("require_native_crypto"):
            native = node_status.get("native_crypto") or {}
            if native.get("required") and not (
                native.get("available") and native.get("self_test")
            ):
                errors.append("/status native_crypto not ready on prod node")
            elif not native.get("required"):
                errors.append("/status require_native_crypto is false on prod node")
        chain_id = int(node_status.get("chain_id", 0) or 0)
        checks["chain_id_mainnet_v1"] = chain_id == MAINNET_V1_CHAIN_ID
        if chain_id != MAINNET_V1_CHAIN_ID:
            errors.append(f"/status chain_id={chain_id}, expected {MAINNET_V1_CHAIN_ID}")
        if not node_status.get("state_root_strict_p2p", True):
            errors.append("/status state_root_strict_p2p is false on prod node")
        consensus = node_status.get("consensus") or {}
        mode = str(consensus.get("mode", "") or "").lower()
        checks["consensus_unified"] = mode == "unified"
        if mode != "unified":
            errors.append(f"/status consensus.mode={mode!r}, expected unified")
        ceremony = node_status.get("genesis_ceremony") or {}
        if ceremony:
            checks["genesis_ceremony_ready"] = bool(ceremony.get("ready"))
            if not ceremony.get("ready"):
                errors.append(f"/status genesis_ceremony not ready: {ceremony.get('errors', [])}")
            pinned = (__import__("os").environ.get("GENESIS_CEREMONY_HASH", "") or "").strip()
            live_hash = str(ceremony.get("ceremony_hash", "") or "")
            if (
                not ceremony.get("ready")
                and pinned
                and live_hash
                and pinned != live_hash
            ):
                errors.append("genesis_ceremony_hash_mismatch: node vs GENESIS_CEREMONY_HASH env")
        else:
            checks["genesis_ceremony_ready"] = False
            errors.append("/status missing genesis_ceremony block")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        errors.append(f"/status unreachable: {exc}")
        checks["status_http"] = False

    try:
        status, ready = _fetch(f"{base}/health/ready")
        checks["health_ready_http"] = status == 200
        checks["health_ready_body"] = ready.get("status") == "ready"
        if status != 200 or ready.get("status") != "ready":
            errors.append(f"/health/ready not ready: status={status} body={ready!r}")
        rust = (ready.get("rust_bridge") or {})
        if bridge_enabled and rust.get("required") and not rust.get("ok"):
            errors.append(f"rust bridge not ok: {rust}")
        l1 = (ready.get("l1_rpc") or {})
        if bridge_enabled and l1.get("required") and not l1.get("ok"):
            errors.append(f"l1 rpc not ok: {l1}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        errors.append(f"/health/ready unreachable: {exc}")
        checks["health_ready_http"] = False

    if bridge_enabled:
        try:
            status, bridge = _fetch(f"{base}/bridge")
            checks["bridge_http"] = status == 200
            mode = bridge.get("mode")
            checks["bridge_rust_mode"] = mode == "rust"
            if mode != "rust":
                errors.append(f"/bridge mode={mode!r}, expected rust")
            l1 = bridge.get("l1_rpc") or {}
            if l1.get("required") and not l1.get("ok"):
                errors.append(f"/bridge l1_rpc not ok: {l1}")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            errors.append(f"/bridge unreachable: {exc}")
            checks["bridge_http"] = False

        try:
            status, relayer = _fetch(f"{base}/bridge/relayer/status")
            checks["relayer_status_http"] = status == 200
            if not relayer.get("oracle_hmac_configured"):
                errors.append("relayer status: oracle HMAC not configured on node")
            if relayer.get("require_l1_proof") and relayer.get("blind_pending_confirm_allowed"):
                errors.append("relayer: blind pending confirm must be disabled in L1-proof mode")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            errors.append(f"/bridge/relayer/status unreachable: {exc}")
            checks["relayer_status_http"] = False
    else:
        checks["bridge_disabled"] = True

    try:
        status, features = _fetch(f"{base}/features")
        checks["features_http"] = status == 200
        wasm = (features.get("wasm") or {})
        if wasm.get("enabled"):
            errors.append("/features wasm must be disabled in prod")
        if wasm.get("tier") == "r-and-d" and not wasm.get("prod_blocked_reason"):
            errors.append("/features wasm missing prod_blocked_reason")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        errors.append(f"/features unreachable: {exc}")
        checks["features_http"] = False

    try:
        status, harness = _fetch(f"{base}/chain/consistency/harness")
        checks["consistency_harness_http"] = status == 200
        if not harness.get("harness_healthy", True):
            errors.append(
                f"/chain/consistency/harness unhealthy: {harness.get('failed_checks', [])}"
            )
        if harness.get("canonical_state_root_source") != "blockchain.database":
            errors.append("harness missing canonical_state_root_source=blockchain.database")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        errors.append(f"/chain/consistency/harness unreachable: {exc}")
        checks["consistency_harness_http"] = False

    try:
        req = urllib.request.Request(f"{base}/metrics")
        with urllib.request.urlopen(req, timeout=8) as resp:
            text = resp.read().decode()
        checks["metrics_http"] = resp.status == 200
        for needle in ("abs_native_crypto_self_test",):
            if needle not in text:
                errors.append(f"/metrics missing {needle}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        errors.append(f"/metrics unreachable: {exc}")
        checks["metrics_http"] = False

    return {"ok": not errors, "errors": errors, "checks": checks, "base": base}


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"
    report = run_prod_smoke(base)
    if report["ok"]:
        print(f"OK: prod smoke {base}")
        return 0
    print(f"FAIL: prod smoke {base}")
    for err in report["errors"]:
        print(f"  - {err}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
