#!/usr/bin/env python3
"""Validate Kubernetes prod manifests for mainnet-ready settings."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
K8S = ROOT / "deploy" / "k8s"


def main() -> int:
    from runtime.mainnet_constants import MAINNET_V1_CHAIN_ID

    errors: list[str] = []

    cfg_path = K8S / "node.prod.k8s.json"
    if not cfg_path.is_file():
        errors.append("missing deploy/k8s/node.prod.k8s.json")
    else:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        if cfg.get("deployment_mode") != "prod":
            errors.append("node.prod.k8s.json: deployment_mode must be prod")
        if int(cfg.get("chain_id", 0) or 0) != MAINNET_V1_CHAIN_ID:
            errors.append(f"node.prod.k8s.json: chain_id must be {MAINNET_V1_CHAIN_ID}")
        if cfg.get("db_engine") != "rocksdb":
            errors.append("node.prod.k8s.json: db_engine must be rocksdb")
        if not cfg.get("follower_genesis_sync"):
            errors.append("node.prod.k8s.json: follower_genesis_sync required for k8s scale-out")
        if cfg.get("p2p_tls_enabled") is not True:
            errors.append("node.prod.k8s.json: p2p_tls_enabled must be true")
        for key in ("p2p_tls_cert_path", "p2p_tls_key_path", "p2p_tls_ca_path"):
            if not str(cfg.get(key) or "").strip():
                errors.append(f"node.prod.k8s.json: {key} required when P2P TLS enabled")

    cm = (K8S / "configmap.yaml").read_text(encoding="utf-8")
    if 'DEPLOYMENT_MODE: "prod"' not in cm:
        errors.append("configmap.yaml: DEPLOYMENT_MODE must be prod")
    if 'DB_ENGINE: "rocksdb"' not in cm:
        errors.append("configmap.yaml: DB_ENGINE must be rocksdb")
    if f'CHAIN_ID: "{MAINNET_V1_CHAIN_ID}"' not in cm:
        errors.append(f"configmap.yaml: CHAIN_ID must be {MAINNET_V1_CHAIN_ID}")
    if "ABS_REQUIRE_NATIVE_CRYPTO" not in cm:
        errors.append("configmap.yaml: ABS_REQUIRE_NATIVE_CRYPTO required")
    if "REDIS_RATE_LIMIT" not in cm:
        errors.append("configmap.yaml: REDIS_RATE_LIMIT required")
    if "REDIS_URL" not in cm:
        errors.append("configmap.yaml: REDIS_URL required")

    redis_yaml = (K8S / "redis.yaml").read_text(encoding="utf-8")
    if "readinessProbe" not in redis_yaml or "redis-cli" not in redis_yaml:
        errors.append("redis.yaml: readinessProbe with redis-cli ping required")
    if "livenessProbe" not in redis_yaml:
        errors.append("redis.yaml: livenessProbe required")

    sts = (K8S / "statefulset.yaml").read_text(encoding="utf-8")
    if "readinessProbe" not in sts or "/health/ready" not in sts:
        errors.append("statefulset.yaml: readinessProbe /health/ready required")
    if "livenessProbe" not in sts or "/health/live" not in sts:
        errors.append("statefulset.yaml: livenessProbe /health/live required")
    if "entrypoint.sh" not in sts:
        errors.append("statefulset.yaml: must use deploy/k8s/entrypoint.sh")
    if "wait-redis" not in sts:
        errors.append("statefulset.yaml: initContainer wait-redis required")
    if "abs-p2p-tls" not in sts or "p2p_tls_secrets" not in sts:
        errors.append("statefulset.yaml: abs-p2p-tls secret mount required")
    if "projected:" not in sts or "abs-p2p-tls-node-0" not in sts:
        errors.append("statefulset.yaml: projected per-pod P2P TLS secrets required")

    cm_json_start = cm.find("node.prod.k8s.json:")
    if cm_json_start < 0:
        errors.append("configmap.yaml: embedded node.prod.k8s.json missing")
    else:
        cm_json_blob = cm[cm_json_start:]
        for key in (
            "p2p_tls_enabled",
            "redis_rate_limit_enabled",
            "redis_url",
            "p2p_tls_cert_path",
        ):
            if key not in cm_json_blob:
                errors.append(f"configmap.yaml: embedded node JSON missing {key}")

    entry = (K8S / "entrypoint.sh").read_text(encoding="utf-8")
    if "p2p_tls_secrets" not in entry:
        errors.append("entrypoint.sh: must wire P2P TLS secrets by pod ordinal")

    cert_mgr = K8S / "cert-manager-p2p.example.yaml"
    if not cert_mgr.is_file():
        errors.append("missing deploy/k8s/cert-manager-p2p.example.yaml")
    elif "cert-manager.io/v1" not in cert_mgr.read_text(encoding="utf-8"):
        errors.append("cert-manager-p2p.example.yaml: must document cert-manager Certificate")

    perpod = K8S / "cert-manager-p2p-perpod.example.yaml"
    if not perpod.is_file():
        errors.append("missing deploy/k8s/cert-manager-p2p-perpod.example.yaml")
    else:
        perpod_txt = perpod.read_text(encoding="utf-8")
        for ordinal in ("abs-node-0-p2p-tls", "abs-node-1-p2p-tls", "abs-node-2-p2p-tls"):
            if ordinal not in perpod_txt:
                errors.append(f"cert-manager-p2p-perpod.example.yaml: missing {ordinal}")

    if errors:
        print("FAIL: k8s prod gate")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("OK: k8s prod gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
