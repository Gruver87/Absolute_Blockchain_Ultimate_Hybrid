#!/usr/bin/env python3
"""Preflight checks before enabling prod L1 bridge (Rust CLI + RPC)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run_preflight(*, config_path: str = "node.prod.mainnet-v1.example.json") -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    cfg_path = Path(config_path)
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path
    if not cfg_path.is_file():
        return [f"config_missing:{cfg_path}"], []

    cfg_data = json.loads(cfg_path.read_text(encoding="utf-8"))
    bridge_enabled = bool(cfg_data.get("bridge_enabled", False))
    bridge_mode = str(cfg_data.get("bridge_mode", "rust") or "rust")

    if not bridge_enabled:
        warnings.append(
            "bridge_disabled: mainnet-v1 profile keeps bridge off until L1 contracts are deployed"
        )
        return errors, warnings

    from runtime.config import Config

    placeholders = {
        "JWT_SECRET": "Q" * 40,
        "RPC_API_KEYS": "R" * 40,
        "BRIDGE_ORACLE_SECRET": "S" * 40,
        "ETH_RPC_URL": os.environ.get("ETH_RPC_URL", "") or "https://rpc.example.com",
        "CORS_ORIGINS": "https://explorer.example.com",
        "BRIDGE_PROBE_L1_RPC": "false",
    }
    saved = {key: os.environ.get(key) for key in placeholders}
    try:
        for key, value in placeholders.items():
            if value:
                os.environ[key] = value
        cfg = Config.from_json(str(cfg_path))
        cfg.apply_env()
        val_errors = cfg.validate()
        bridge_errors = [
            e for e in val_errors
            if "bridge" in e.lower() or "rpc" in e.lower() or "l1" in e.lower()
        ]
        errors.extend(bridge_errors)
    finally:
        for key, old in saved.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old

    if bridge_mode == "rust":
        from bridge.health import check_rust_bridge_binary

        bin_path = cfg.resolve_rust_bridge_path()
        if not os.path.isfile(bin_path):
            errors.append(f"rust_bridge_missing:{bin_path}")
        else:
            status = check_rust_bridge_binary(bin_path)
            if not status.get("ok"):
                errors.append(f"rust_bridge_unhealthy:{status.get('error', status)}")

    eth_rpc = os.environ.get("ETH_RPC_URL", "").strip()
    if not eth_rpc:
        warnings.append("ETH_RPC_URL not set in environment (required at deploy when bridge_enabled)")

    if os.environ.get("BRIDGE_ALLOW_SYNTHETIC", "").strip() in ("1", "true", "yes"):
        errors.append("prod forbids BRIDGE_ALLOW_SYNTHETIC")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Prod L1 bridge preflight")
    parser.add_argument(
        "--config",
        default="node.prod.mainnet-v1.example.json",
        help="Prod node config JSON",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    errors, warnings = run_preflight(config_path=args.config)
    payload = {"ok": not errors, "errors": errors, "warnings": warnings}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("Bridge L1 preflight")
        print("=" * 60)
        for err in errors:
            print(f"  FAIL: {err}")
        for warn in warnings:
            print(f"  WARN: {warn}")
        if not errors:
            print("OK: bridge preflight passed" if not warnings else "OK: bridge preflight (see warnings)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
