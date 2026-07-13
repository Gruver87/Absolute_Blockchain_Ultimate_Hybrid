#!/usr/bin/env python3
"""Verify public testnet Docker mesh (seed + optional validator on :19080/:19081)."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED = "http://127.0.0.1:19080"
DEFAULT_VALIDATOR = "http://127.0.0.1:19081"
EXPECTED_CHAIN_ID = 77777


def _api(url: str, timeout: float = 10.0) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _probe_health(base_url: str, timeout: float = 5.0) -> bool:
    try:
        row = _api(f"{base_url.rstrip('/')}/health/ready", timeout=timeout)
        return str(row.get("status", "")).lower() == "ready"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return False


def verify_testnet_mesh(
    *,
    seed_url: str = DEFAULT_SEED,
    validator_url: str = "",
    wait_sec: int = 0,
) -> tuple[list[str], list[str], dict[str, Any]]:
    import time

    errors: list[str] = []
    warnings: list[str] = []
    urls = [seed_url.rstrip("/")]
    if validator_url:
        urls.append(validator_url.rstrip("/"))

    deadline = time.time() + max(0, wait_sec)
    reachable: list[str] = []
    while True:
        reachable = [u for u in urls if _probe_health(u)]
        if len(reachable) == len(urls) or time.time() >= deadline:
            break
        time.sleep(3)

    nodes: list[dict[str, Any]] = []
    for i, url in enumerate(urls, start=1):
        row: dict[str, Any] = {"url": url, "role": "seed" if i == 1 else f"validator{i - 1}"}
        if url not in reachable:
            errors.append(f"node{i} not reachable at {url}")
            nodes.append(row)
            continue
        row["reachable"] = True
        try:
            st = _api(f"{url}/status", timeout=10)
            row["height"] = int(st.get("height", 0) or 0)
            row["peers"] = int(st.get("peers", st.get("peer_count", 0)) or 0)
            row["chain_id"] = int(st.get("chain_id", 0) or 0)
            if row["chain_id"] != EXPECTED_CHAIN_ID:
                errors.append(f"node{i} chain_id={row['chain_id']} expected {EXPECTED_CHAIN_ID}")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"node{i} /status: {exc}")
        try:
            harness = _api(f"{url}/chain/consistency/harness?quick=1&peer_timeout=5", timeout=25)
            row["harness_healthy"] = bool(harness.get("harness_healthy"))
            row["tip_state_aligned"] = bool(harness.get("tip_state_aligned"))
            if not row["harness_healthy"]:
                errors.append(f"node{i} harness unhealthy")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            warnings.append(f"node{i} harness: {exc}")
        nodes.append(row)

    if len(reachable) >= 2:
        heights = [n.get("height", 0) for n in nodes if n.get("reachable")]
        if heights and max(heights) - min(heights) > 1:
            errors.append(f"height spread across mesh: {heights}")

    meta_mesh: dict[str, Any] = {}
    if reachable:
        leader = reachable[0]
        try:
            mesh = _api(f"{leader}/testnet/mesh", timeout=12)
            meta_mesh = {
                "peer_count": mesh.get("peer_count"),
                "expected_peers": mesh.get("expected_peers"),
                "mesh_healthy": mesh.get("mesh_healthy"),
                "height_aligned": mesh.get("height_aligned"),
            }
            if len(reachable) >= 2 and not mesh.get("mesh_healthy"):
                errors.append(
                    f"seed mesh_healthy=false peer_count={mesh.get('peer_count')} "
                    f"expected={mesh.get('expected_peers')}"
                )
            elif len(reachable) == 1:
                warnings.append("solo seed — start validator profile for 2-node mesh demo")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"seed /testnet/mesh: {exc}")

    meta: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "chain_id": EXPECTED_CHAIN_ID,
        "nodes": nodes,
        "reachable": len(reachable),
        "expected": len(urls),
        "mesh": meta_mesh,
        "ready": not errors,
    }

    return errors, warnings, meta


def write_report(errors: list[str], warnings: list[str], meta: dict[str, Any]) -> Path:
    out = ROOT / "logs" / "testnet_mesh_verify.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ok": not errors, "errors": errors, "warnings": warnings, **meta}
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify public testnet mesh (chain 77777)")
    parser.add_argument("--seed-url", default=DEFAULT_SEED)
    parser.add_argument("--validator-url", default="", help="Optional second node (e.g. :19081)")
    parser.add_argument("--mesh", action="store_true", help="Require validator URL :19081")
    parser.add_argument("--wait", type=int, default=0, help="Seconds to wait for nodes")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    validator = args.validator_url
    if args.mesh and not validator:
        validator = DEFAULT_VALIDATOR

    errors, warnings, meta = verify_testnet_mesh(
        seed_url=args.seed_url,
        validator_url=validator,
        wait_sec=args.wait,
    )
    report = write_report(errors, warnings, meta)

    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors, "warnings": warnings, "report": str(report), **meta}, indent=2))
    else:
        print("=" * 60)
        print("TESTNET MESH VERIFY (chain 77777)")
        print("=" * 60)
        if errors:
            print("RESULT: FAIL")
            for err in errors:
                print(f"  - {err}")
        else:
            print("RESULT: OK")
        for warn in warnings:
            print(f"  WARN: {warn}")
        print(f"Report: {report}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
