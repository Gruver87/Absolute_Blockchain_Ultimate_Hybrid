#!/usr/bin/env python3
"""Bridge L1 cutover gate — static preflight + optional live prod checks."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_BRIDGE_CONFIG = "node.prod.mainnet-v1.bridge.example.json"


def is_placeholder_rpc_url(url: str) -> bool:
    from bridge.l1_rpc import is_placeholder_l1_rpc_url

    return is_placeholder_l1_rpc_url(url)


def resolve_live_base_url(preferred: str = "") -> str:
    """Pick Docker alt port (18080) or default 8080 when prod node is reachable."""
    if preferred:
        return preferred.rstrip("/")
    from runtime.mainnet_constants import MAINNET_V1_CHAIN_ID

    bridge_ready = ""
    prod_ready = ""
    for port in (18080, 8080):
        base = f"http://127.0.0.1:{port}"
        try:
            with urllib.request.urlopen(f"{base}/status", timeout=3) as resp:
                data = json.loads(resp.read().decode())
            if (
                str(data.get("deployment_mode", "")) == "prod"
                and int(data.get("chain_id", 0) or 0) == MAINNET_V1_CHAIN_ID
            ):
                if not prod_ready:
                    prod_ready = base
                if bool(data.get("bridge_enabled", False)):
                    bridge_ready = base
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            continue
    return bridge_ready or prod_ready or "http://127.0.0.1:18080"


def _fetch_status(base_url: str) -> Dict[str, Any]:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}/status", timeout=5) as resp:
        return json.loads(resp.read().decode())


def check_live_bridge_cutover(base_url: str) -> Tuple[List[str], List[str]]:
    """Live HTTP checks for bridge-enabled prod node."""
    errors: List[str] = []
    warnings: List[str] = []
    base = base_url.rstrip("/")

    try:
        status = _fetch_status(base)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        errors.append(f"cannot read /status from {base}: {exc}")
        return errors, warnings

    if not bool(status.get("bridge_enabled", False)):
        errors.append(
            "node has bridge_enabled=false — set a real ETH_RPC_URL in .env, then run "
            ".\\scripts\\docker_prod.ps1 -Bridge (or docker compose --profile bridge)"
        )
        return errors, warnings

    sys.path.insert(0, str(ROOT / "scripts"))
    import prod_smoke

    report = prod_smoke.run_prod_smoke(base)
    for err in report.get("errors") or []:
        low = err.lower()
        if any(token in low for token in ("bridge", "relayer", "l1", "rust bridge")):
            errors.append(err)
    if not report.get("checks", {}).get("bridge_rust_mode"):
        errors.append("live: /bridge mode must be rust on cutover node")

    try:
        proc = __import__("subprocess").run(
            [sys.executable, str(ROOT / "scripts" / "bridge_relayer.py"), "--preflight", "--api", base],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            detail = (proc.stdout or proc.stderr or "").strip()
            errors.append(f"bridge_relayer preflight failed: {detail or proc.returncode}")
    except Exception as exc:
        warnings.append(f"bridge_relayer preflight skipped: {exc}")

    return errors, warnings


def run_cutover_gate(
    *,
    config_path: str = _BRIDGE_CONFIG,
    live: bool = False,
    base_url: str = "",
    probe_l1: bool = False,
) -> Tuple[List[str], List[str], Dict[str, Any]]:
    from bridge_l1_preflight import run_preflight

    errors: List[str] = []
    warnings: List[str] = []
    meta: Dict[str, Any] = {"config_path": config_path, "live": live, "probe_l1": probe_l1}

    pre_errors, pre_warnings = run_preflight(
        config_path=config_path,
        probe_l1=probe_l1,
    )
    errors.extend(pre_errors)
    warnings.extend(pre_warnings)
    meta["eth_rpc_configured"] = bool(os.environ.get("ETH_RPC_URL", "").strip())

    if live:
        live_base = resolve_live_base_url(base_url)
        meta["base_url"] = live_base
        live_errors, live_warnings = check_live_bridge_cutover(live_base)
        errors.extend([f"live:{e}" for e in live_errors])
        warnings.extend(live_warnings)

    meta["ok"] = not errors
    return errors, warnings, meta


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge L1 mainnet cutover gate")
    parser.add_argument(
        "--config",
        default=_BRIDGE_CONFIG,
        help="Bridge-enabled prod node JSON",
    )
    parser.add_argument("--live", action="store_true", help="Probe running prod node HTTP API")
    parser.add_argument("--base-url", default="", help="Override live base URL")
    parser.add_argument(
        "--probe-l1",
        action="store_true",
        help="Run eth_blockNumber probe during static preflight",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    errors, warnings, meta = run_cutover_gate(
        config_path=args.config,
        live=args.live,
        base_url=args.base_url,
        probe_l1=args.probe_l1 or args.live,
    )

    if args.json:
        print(json.dumps({"errors": errors, "warnings": warnings, **meta}, indent=2))
    else:
        print("=" * 60)
        print("BRIDGE L1 CUTOVER GATE")
        print("=" * 60)
        if errors:
            print("RESULT: FAIL")
            for err in errors:
                print(f"  - {err}")
            if any("401" in e for e in errors):
                print()
                print("Infura 401 = invalid API key. Dashboard -> Project -> API Key (32 hex characters).")
                print('  .\\scripts\\setup_prod_env.ps1 -Force -EthRpcUrl "https://mainnet.infura.io/v3/<API_KEY>"')
            if any("placeholder" in e.lower() for e in errors):
                print()
                print("Fix ETH_RPC_URL (real Ethereum JSON-RPC, not rpc.example.com):")
                print('  .\\scripts\\setup_prod_env.ps1 -Force -EthRpcUrl "https://<your-provider>"')
                print("  .\\scripts\\docker_prod.ps1 -Bridge")
                print("  .\\scripts\\bridge_l1_cutover.ps1 -ProbeL1 -BaseUrl http://127.0.0.1:18080")
            if args.live and any("bridge_enabled=false" in e for e in errors):
                print()
                print("Live cutover requires bridge-enabled prod node on :18080 (see above).")
        else:
            print("RESULT: OK — static cutover checks passed")
        if warnings:
            print("\nWarnings:")
            for warn in warnings:
                print(f"  ! {warn}")
        if args.live and meta.get("base_url"):
            print(f"\nLive base: {meta['base_url']}")
        print("=" * 60)

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
