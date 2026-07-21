#!/usr/bin/env python3
"""
Bridge relayer worker — polls pending locks and confirms via oracle HMAC API.

Usage:
  set BRIDGE_ORACLE_SECRET=your_secret
  set ABS_API_URL=http://127.0.0.1:8080
  python scripts/bridge_relayer.py --once
  python scripts/bridge_relayer.py --interval 30
  python scripts/bridge_relayer.py --once --watch-l1
  python scripts/bridge_relayer.py --preflight
  set ETH_RPC_URL=https://...
  set BRIDGE_L1_QUEUE_PATH=data/bridge_l1_queue.json
  set BRIDGE_REQUIRE_L1_PROOF=true   # prod: only L1-backed confirm via --watch-l1
"""
from __future__ import annotations

import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bridge.relayer import (
    check_relayer_readiness,
    http_get_json,
    oracle_post,
    process_l1_queue,
    process_pending,
    relayer_require_l1_proof,
)

is_tx_confirmed = __import__("bridge.l1_rpc", fromlist=["is_tx_confirmed"]).is_tx_confirmed


def _oracle_post(base, path, payload, secret):
    return oracle_post(base, path, payload, secret)


def main() -> int:
    parser = argparse.ArgumentParser(description="ABS bridge relayer (oracle HMAC + optional L1 watch)")
    parser.add_argument("--api", default=os.getenv("ABS_API_URL", "http://127.0.0.1:8080"))
    parser.add_argument("--secret", default=os.getenv("BRIDGE_ORACLE_SECRET", ""))
    parser.add_argument("--interval", type=int, default=0, help="Poll interval sec (0 = once)")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Run readiness checks and exit (0=ok, 1=fail)",
    )
    parser.add_argument(
        "--watch-l1",
        action="store_true",
        help="Also poll BRIDGE_L1_QUEUE_PATH items against L1 RPC (ETH_RPC_URL, etc.)",
    )
    parser.add_argument(
        "--allow-blind-confirm",
        action="store_true",
        help="Allow confirming pending locks without L1 proofs even when BRIDGE_REQUIRE_L1_PROOF=true (dev only)",
    )
    parser.add_argument(
        "--l1-queue",
        default=os.getenv("BRIDGE_L1_QUEUE_PATH", "data/bridge_l1_queue.json"),
        help="JSON queue: outbound/incoming L1 proofs",
    )
    args = parser.parse_args()

    if not args.secret:
        print("BRIDGE_ORACLE_SECRET required")
        return 1

    if args.preflight:
        report = check_relayer_readiness(args.api, args.secret)
        if report["ok"]:
            print("OK: relayer preflight")
            return 0
        print("FAIL: relayer preflight")
        for err in report.get("errors", []):
            print(f"  - {err}")
        return 1

    require_l1 = relayer_require_l1_proof()
    if require_l1 and not args.watch_l1:
        # In L1-proof mode, blind confirmation is unsafe. Fail closed unless explicitly allowed.
        if not args.allow_blind_confirm:
            print(
                "FAIL: BRIDGE_REQUIRE_L1_PROOF=true — relayer must run with --watch-l1 "
                "(or pass --allow-blind-confirm for dev only)"
            )
            return 1
        # Hard-fail blind confirm against a prod API (deployment_mode from /status).
        try:
            st = http_get_json(f"{args.api.rstrip('/')}/status")
            mode = str(st.get("deployment_mode") or "").strip().lower()
        except Exception as exc:
            print(
                f"FAIL: cannot verify deployment_mode before --allow-blind-confirm: {exc}"
            )
            return 1
        if mode in ("prod", "production"):
            print(
                "FAIL: refusing --allow-blind-confirm against prod API "
                f"(deployment_mode={mode!r}); audited L1 + --watch-l1 required"
            )
            return 1
        print(
            "WARN: allow-blind-confirm enabled while BRIDGE_REQUIRE_L1_PROOF=true "
            f"(non-prod only; deployment_mode={mode!r})"
        )

    interval = 0 if args.once else (args.interval or 0)
    while True:
        try:
            st = http_get_json(f"{args.api.rstrip('/')}/status")
            print(
                f"Relayer tick: height={st.get('height')} bridge={st.get('bridge_mode')} "
                f"pending={st.get('bridge_pending', '?')}"
            )
            n = process_pending(args.api, args.secret, dry_run=args.dry_run)
            if n:
                print(f"Confirmed {n} lock(s)")
            if args.watch_l1:
                l1n = process_l1_queue(args.api, args.secret, args.l1_queue, dry_run=args.dry_run)
                if l1n:
                    print(f"Processed {l1n} L1 queue item(s)")
        except Exception as exc:
            print(f"Relayer error: {exc}")
            if interval <= 0:
                return 2
        if interval <= 0:
            return 0
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
