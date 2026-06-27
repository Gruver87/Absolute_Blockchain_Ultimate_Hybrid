#!/usr/bin/env python3
"""Static production gate for fail-closed prod configuration."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROD_FILES = [
    "docker/node.prod.json",
    "node.prod.example.json",
]

BLOCKED_FEATURES = [
    "feature_zk",
    "feature_sharding",
    "feature_oracles",
    "feature_wasm",
    "feature_plasma",
    "feature_lightning",
    "feature_pq",
    "feature_mev",
    "feature_ai_agents",
]

REQUIRED_TRUE = [
    "require_signatures",
    "enforce_proposer",
    "verify_peer_state_root",
    "rpc_api_key_required",
    "jwt_enforce_admin",
    "require_wallet_file",
    "bridge_require_l1_proof",
]


def load_json(path: str) -> dict:
    with (ROOT / path).open(encoding="utf-8") as f:
        return json.load(f)


def check_file(path: str) -> list[str]:
    cfg = load_json(path)
    errors: list[str] = []

    if cfg.get("deployment_mode") != "prod":
        errors.append(f"{path}: deployment_mode must be prod")
    if cfg.get("bridge_enabled", True) and cfg.get("bridge_mode") != "rust":
        errors.append(f"{path}: prod bridge must use rust mode or be disabled")

    for key in REQUIRED_TRUE:
        if cfg.get(key) is not True:
            errors.append(f"{path}: {key} must be true")

    for key in BLOCKED_FEATURES:
        if cfg.get(key, False):
            errors.append(f"{path}: {key} must be false in prod")

    origins = cfg.get("cors_origins", [])
    if origins == ["*"] or "*" in origins:
        errors.append(f"{path}: wildcard CORS is forbidden in prod")
    if any(str(origin).startswith(("http://localhost", "http://127.")) for origin in origins):
        errors.append(f"{path}: localhost CORS is forbidden in prod")

    return errors


def main() -> int:
    errors: list[str] = []
    for path in PROD_FILES:
        errors.extend(check_file(path))

    if errors:
        print("FAIL: production gate")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("OK: production gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
