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

    cm = (K8S / "configmap.yaml").read_text(encoding="utf-8")
    if 'DEPLOYMENT_MODE: "prod"' not in cm:
        errors.append("configmap.yaml: DEPLOYMENT_MODE must be prod")
    if 'DB_ENGINE: "rocksdb"' not in cm:
        errors.append("configmap.yaml: DB_ENGINE must be rocksdb")
    if f'CHAIN_ID: "{MAINNET_V1_CHAIN_ID}"' not in cm:
        errors.append(f"configmap.yaml: CHAIN_ID must be {MAINNET_V1_CHAIN_ID}")
    if "ABS_REQUIRE_NATIVE_CRYPTO" not in cm:
        errors.append("configmap.yaml: ABS_REQUIRE_NATIVE_CRYPTO required")

    sts = (K8S / "statefulset.yaml").read_text(encoding="utf-8")
    if "readinessProbe" not in sts or "/health/ready" not in sts:
        errors.append("statefulset.yaml: readinessProbe /health/ready required")
    if "livenessProbe" not in sts or "/health/live" not in sts:
        errors.append("statefulset.yaml: livenessProbe /health/live required")
    if "entrypoint.sh" not in sts:
        errors.append("statefulset.yaml: must use deploy/k8s/entrypoint.sh")

    if errors:
        print("FAIL: k8s prod gate")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("OK: k8s prod gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
