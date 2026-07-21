#!/usr/bin/env python3
"""Preflight checks before enabling prod L1 bridge (Rust CLI + RPC)."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_PLACEHOLDER_RPC = re.compile(
    r"(?i)(ваш-ethereum|your-ethereum|your-mainnet|changeme|placeholder|todo|rpc\.example$|example\.com$)"
)


def is_placeholder_rpc_url(url: str) -> bool:
    from runtime.secret_utils import is_placeholder_secret

    url = (url or "").strip()
    if not url:
        return True
    if is_placeholder_secret(url):
        return True
    return bool(_PLACEHOLDER_RPC.search(url))

def _is_placeholder_contract(addr: str) -> bool:
    from runtime.secret_utils import is_placeholder_secret

    a = (addr or "").strip().lower()
    if not a:
        return True
    if is_placeholder_secret(a):
        return True
    if not a.startswith("0x") or len(a) != 42:
        return True
    try:
        raw = bytes.fromhex(a[2:])
    except ValueError:
        return True
    return raw == b"\x00" * 20


def run_preflight(
    *,
    config_path: str = "node.prod.mainnet-v1.example.json",
    probe_l1: bool = False,
    probe_l1_rpc_only: bool = False,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    rpc_probe = probe_l1 or probe_l1_rpc_only
    strict_contracts = probe_l1 and not probe_l1_rpc_only

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
        "BRIDGE_PROBE_L1_RPC": "true" if rpc_probe else "false",
    }
    saved = {key: os.environ.get(key) for key in placeholders}
    saved_probe = os.environ.get("BRIDGE_PROBE_L1_RPC")
    try:
        for key, value in placeholders.items():
            if value is not None and value != "":
                os.environ[key] = str(value)
        if rpc_probe:
            os.environ["BRIDGE_PROBE_L1_RPC"] = "true"
        cfg = Config.from_json(str(cfg_path))
        cfg.apply_env()
        cfg.apply_env_secrets()
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
        if saved_probe is None:
            os.environ.pop("BRIDGE_PROBE_L1_RPC", None)
        else:
            os.environ["BRIDGE_PROBE_L1_RPC"] = saved_probe

    if bridge_mode == "rust":
        from bridge.health import check_rust_bridge_binary

        probe_cfg = Config.from_json(str(cfg_path))
        probe_cfg.apply_env()
        bin_path = probe_cfg.resolve_rust_bridge_path()
        if not os.path.isfile(bin_path):
            errors.append(f"rust_bridge_missing:{bin_path}")
        else:
            status = check_rust_bridge_binary(bin_path)
            if not status.get("ok"):
                errors.append(f"rust_bridge_unhealthy:{status.get('error', status)}")

    eth_rpc = os.environ.get("ETH_RPC_URL", "").strip()
    if not eth_rpc:
        if rpc_probe:
            errors.append("ETH_RPC_URL not set in environment (required when bridge_enabled)")
        else:
            warnings.append("ETH_RPC_URL not set (static preflight); required for live cutover")
    elif is_placeholder_rpc_url(eth_rpc):
        if rpc_probe:
            errors.append("ETH_RPC_URL looks like a placeholder, not production RPC")
        else:
            warnings.append("ETH_RPC_URL looks like a placeholder (static preflight); required for live cutover")
    elif rpc_probe:
        from bridge.health import check_l1_rpc_health

        probe_cfg = Config.from_json(str(cfg_path))
        probe_cfg.deployment_mode = "prod"
        probe_cfg.bridge_enabled = True
        probe_cfg.bridge_require_l1_proof = True
        os.environ["BRIDGE_PROBE_L1_RPC"] = "true"
        l1 = check_l1_rpc_health(probe_cfg, timeout=5.0)
        if l1.get("required") and not l1.get("ok"):
            errors.append(f"l1_rpc_probe_failed:{l1.get('error', l1)}")

    if os.environ.get("BRIDGE_ALLOW_SYNTHETIC", "").strip().lower() in ("1", "true", "yes"):
        errors.append("prod forbids BRIDGE_ALLOW_SYNTHETIC")

    # L1 contract addresses (cutover profile).
    lock_addr = (
        str(os.environ.get("BRIDGE_L1_LOCK_CONTRACT", "") or "").strip()
        or str(cfg_data.get("bridge_l1_lock_contract", "") or "").strip()
    )
    mint_addr = (
        str(os.environ.get("BRIDGE_L1_MINT_CONTRACT", "") or "").strip()
        or str(cfg_data.get("bridge_l1_mint_contract", "") or "").strip()
    )
    if not lock_addr or _is_placeholder_contract(lock_addr):
        msg = "BRIDGE_L1_LOCK_CONTRACT missing/placeholder (required for real cutover)"
        (errors if strict_contracts else warnings).append(msg)
    if not mint_addr or _is_placeholder_contract(mint_addr):
        msg = "BRIDGE_L1_MINT_CONTRACT missing/placeholder (required for real cutover)"
        (errors if strict_contracts else warnings).append(msg)

    if strict_contracts and not errors:
        # Validate that contracts are actually deployed (non-empty bytecode).
        from bridge.l1_rpc import chain_rpc_url, get_contract_code

        chain = (
            str(os.environ.get("BRIDGE_L1_CHAIN", "") or "").strip()
            or str(cfg_data.get("bridge_l1_chain", "") or "").strip()
            or "ethereum"
        )
        rpc = chain_rpc_url(chain) or os.environ.get("ETH_RPC_URL", "").strip()
        if not rpc:
            errors.append("BRIDGE_L1_CHAIN RPC not configured (set ETH_RPC_URL/BSC_RPC_URL/POLYGON_RPC_URL)")
        else:
            try:
                lock_code = get_contract_code(rpc, lock_addr, timeout=10.0)
                mint_code = get_contract_code(rpc, mint_addr, timeout=10.0)
            except Exception as exc:
                errors.append(f"L1 eth_getCode probe failed: {exc}")
                return errors, warnings
            if lock_code in ("0x", "0x0", ""):
                errors.append("L1 lock contract has empty bytecode (eth_getCode=0x)")
            if mint_code in ("0x", "0x0", ""):
                errors.append("L1 mint contract has empty bytecode (eth_getCode=0x)")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Prod L1 bridge preflight")
    parser.add_argument(
        "--config",
        default="node.prod.mainnet-v1.example.json",
        help="Prod node config JSON",
    )
    parser.add_argument(
        "--probe-l1",
        action="store_true",
        help="Run eth_blockNumber against configured ETH_RPC_URL",
    )
    parser.add_argument(
        "--probe-l1-rpc-only",
        action="store_true",
        help="Probe L1 RPC only (skip contract bytecode until addresses are set)",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    errors, warnings = run_preflight(
        config_path=args.config,
        probe_l1=args.probe_l1,
        probe_l1_rpc_only=args.probe_l1_rpc_only,
    )
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
