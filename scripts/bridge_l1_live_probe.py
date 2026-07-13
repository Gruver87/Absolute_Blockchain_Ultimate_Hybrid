#!/usr/bin/env python3
"""Unified L1 bridge live probe — static, --probe-l1 RPC, and optional live node checks."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

_DEFAULT_CONFIG = "node.prod.mainnet-v1.bridge.example.json"


def run_bridge_l1_live_probe(
    *,
    config_path: str = _DEFAULT_CONFIG,
    probe_l1: bool = False,
    probe_l1_rpc_only: bool = False,
    live: bool = False,
    base_url: str = "",
) -> tuple[list[str], list[str], dict]:
    from bridge_l1_cutover import resolve_live_base_url, run_cutover_gate

    live_base = resolve_live_base_url(base_url) if live else (base_url.rstrip("/") if base_url else "")
    errors, warnings, meta = run_cutover_gate(
        config_path=config_path,
        live=live,
        base_url=live_base,
        probe_l1=probe_l1,
        probe_l1_rpc_only=probe_l1_rpc_only,
    )
    rpc_probe = probe_l1 or probe_l1_rpc_only
    meta = {
        **meta,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config_path": config_path,
        "probe_l1": probe_l1,
        "probe_l1_rpc_only": probe_l1_rpc_only,
        "live": live,
        "mode": (
            "full"
            if probe_l1 and live
            else "probe-l1"
            if probe_l1
            else "probe-l1-rpc-only"
            if probe_l1_rpc_only
            else "live"
            if live
            else "static"
        ),
    }
    return errors, warnings, meta


def write_report(errors: list[str], warnings: list[str], meta: dict) -> Path:
    out = ROOT / "logs" / "bridge_l1_live_probe.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        **meta,
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="L1 bridge live probe (static / probe-l1 / live / full)"
    )
    parser.add_argument("--config", default=_DEFAULT_CONFIG)
    parser.add_argument(
        "--probe-l1",
        action="store_true",
        help="Probe ETH_RPC_URL (eth_blockNumber) and L1 contract bytecode",
    )
    parser.add_argument(
        "--probe-l1-rpc-only",
        action="store_true",
        help="Probe ETH_RPC_URL only (skip contract bytecode until addresses are set)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Live checks against bridge-enabled prod node HTTP API",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Shorthand for --probe-l1 --live",
    )
    parser.add_argument("--base-url", default="", help="Override live prod base URL")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    probe_l1 = args.probe_l1 or args.full
    probe_l1_rpc_only = args.probe_l1_rpc_only and not probe_l1
    live = args.live or args.full

    errors, warnings, meta = run_bridge_l1_live_probe(
        config_path=args.config,
        probe_l1=probe_l1,
        probe_l1_rpc_only=probe_l1_rpc_only,
        live=live,
        base_url=args.base_url,
    )
    report_path = write_report(errors, warnings, meta)

    if args.json:
        print(
            json.dumps(
                {
                    "ok": not errors,
                    "errors": errors,
                    "warnings": warnings,
                    "report": str(report_path),
                    **meta,
                },
                indent=2,
            )
        )
    else:
        print("=" * 60)
        print(f"BRIDGE L1 LIVE PROBE ({meta.get('mode', 'static')})")
        print("=" * 60)
        if errors:
            print("RESULT: FAIL")
            for err in errors:
                print(f"  - {err}")
        else:
            print("RESULT: OK")
        for warn in warnings:
            print(f"  WARN: {warn}")
        l1 = meta.get("l1_rpc") or {}
        if l1.get("probes"):
            print("\nL1 RPC probes:")
            for chain, row in (l1.get("probes") or {}).items():
                block = row.get("block_number", "?")
                ok = row.get("ok", False)
                print(f"  {chain}: ok={ok} block={block}")
        if meta.get("base_url"):
            print(f"\nLive base: {meta['base_url']}")
        print(f"\nReport: {report_path}")
        print("=" * 60)

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
