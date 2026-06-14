#!/usr/bin/env python3
"""
Bridge relayer worker — polls pending locks and confirms via oracle HMAC API.

Usage:
  set BRIDGE_ORACLE_SECRET=your_secret
  set ABS_API_URL=http://127.0.0.1:8080
  python scripts/bridge_relayer.py --once
  python scripts/bridge_relayer.py --interval 30
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bridge.oracle_auth import sign_payload


def _get(url: str, timeout: float = 10) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _oracle_post(base: str, path: str, payload: dict, secret: str) -> dict:
    body = json.dumps(payload).encode()
    sig = sign_payload(secret, body)
    req = urllib.request.Request(
        f"{base.rstrip('/')}{path}",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Bridge-Oracle-Signature": sig,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode(), "status": e.code}


def process_pending(base: str, secret: str, dry_run: bool = False) -> int:
    locks = _get(f"{base}/bridge/locks").get("locks", [])
    pending = [l for l in locks if (l.get("status") or "pending") == "pending"]
    if not pending:
        print("No pending bridge locks")
        return 0
    confirmed = 0
    for lock in pending:
        tx = lock.get("tx_hash", "")
        if not tx:
            continue
        print(f"Confirm lock {tx[:16]}… amount={lock.get('amount')} chain={lock.get('to_chain')}")
        if dry_run:
            continue
        result = _oracle_post(base, "/bridge/oracle/confirm-lock", {"tx_hash": tx}, secret)
        if result.get("confirmed") or result.get("success"):
            confirmed += 1
            print(f"  OK: {result}")
        else:
            print(f"  FAIL: {result}")
    return confirmed


def main() -> int:
    parser = argparse.ArgumentParser(description="ABS bridge relayer (oracle HMAC)")
    parser.add_argument("--api", default=os.getenv("ABS_API_URL", "http://127.0.0.1:8080"))
    parser.add_argument("--secret", default=os.getenv("BRIDGE_ORACLE_SECRET", ""))
    parser.add_argument("--interval", type=int, default=0, help="Poll interval sec (0 = once)")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.secret:
        print("BRIDGE_ORACLE_SECRET required")
        return 1

    interval = 0 if args.once else (args.interval or 0)
    while True:
        try:
            st = _get(f"{args.api}/status")
            print(f"Relayer tick: height={st.get('height')} bridge={st.get('bridge_mode')} pending={st.get('bridge_pending', '?')}")
            n = process_pending(args.api, args.secret, dry_run=args.dry_run)
            if n:
                print(f"Confirmed {n} lock(s)")
        except Exception as exc:
            print(f"Relayer error: {exc}")
            if interval <= 0:
                return 2
        if interval <= 0:
            return 0
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
