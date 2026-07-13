#!/usr/bin/env python3
"""Lightweight public testnet uptime probe (cron / VPS monitoring)."""

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
DEFAULT_BASE = "http://127.0.0.1:19080"
EXPECTED_CHAIN_ID = 77777


def _get_json(url: str, timeout: float = 8.0) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def run_testnet_uptime_probe(
    *,
    base_url: str = DEFAULT_BASE,
    quick_harness: bool = True,
) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    base = base_url.rstrip("/")
    meta: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "base_url": base,
        "chain_id_expected": EXPECTED_CHAIN_ID,
    }

    try:
        ready = _get_json(f"{base}/health/ready")
        meta["ready"] = ready
        if str(ready.get("status", "")).lower() != "ready":
            errors.append(f"health/ready status={ready.get('status')!r}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"health/ready: {exc}")
        meta["ok"] = False
        return errors, warnings, meta

    try:
        status = _get_json(f"{base}/status")
        meta["status"] = {
            "chain_id": status.get("chain_id"),
            "height": status.get("height"),
            "peers": status.get("peers", status.get("peer_count")),
            "head_hash": status.get("head_hash"),
            "deployment_mode": status.get("deployment_mode"),
        }
        chain_id = int(status.get("chain_id", 0) or 0)
        if chain_id != EXPECTED_CHAIN_ID:
            errors.append(f"chain_id={chain_id} expected {EXPECTED_CHAIN_ID}")
        peers = int(status.get("peers", status.get("peer_count", 0)) or 0)
        if peers < 1:
            warnings.append(f"peer_count={peers} (solo seed — add validator profile for mesh demo)")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"status: {exc}")

    if quick_harness and not errors:
        try:
            harness = _get_json(f"{base}/chain/consistency/harness?quick=1&peer_timeout=5", timeout=25.0)
            meta["harness"] = {
                "harness_healthy": harness.get("harness_healthy"),
                "tip_state_aligned": harness.get("tip_state_aligned"),
            }
            if not harness.get("harness_healthy"):
                errors.append("harness not healthy")
            if not harness.get("tip_state_aligned"):
                errors.append("tip_state not aligned")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            warnings.append(f"harness: {exc}")

    meta["ok"] = not errors
    return errors, warnings, meta


def write_snapshot(errors: list[str], warnings: list[str], meta: dict[str, Any]) -> Path:
    out = ROOT / "logs" / "testnet_uptime.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"errors": errors, "warnings": warnings, **meta}
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def append_history(errors: list[str], warnings: list[str], meta: dict[str, Any]) -> Path:
    out = ROOT / "logs" / "testnet_uptime.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        **meta,
    }
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Public testnet uptime probe")
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--no-harness", action="store_true", help="Skip consistency harness")
    parser.add_argument("--append", action="store_true", help="Append line to logs/testnet_uptime.jsonl")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    errors, warnings, meta = run_testnet_uptime_probe(
        base_url=args.base_url,
        quick_harness=not args.no_harness,
    )
    snapshot = write_snapshot(errors, warnings, meta)
    if args.append:
        append_history(errors, warnings, meta)

    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors, "warnings": warnings, "snapshot": str(snapshot), **meta}, indent=2))
    else:
        mark = "OK" if not errors else "FAIL"
        height = (meta.get("status") or {}).get("height", "?")
        peers = (meta.get("status") or {}).get("peers", "?")
        print(f"{mark}: testnet uptime base={args.base_url} height={height} peers={peers}")
        for err in errors:
            print(f"  - {err}")
        for warn in warnings:
            print(f"  WARN: {warn}")
        print(f"  snapshot: {snapshot}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
