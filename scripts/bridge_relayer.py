#!/usr/bin/env python3
"""
Bridge relayer worker — polls pending locks and confirms via oracle HMAC API.

Usage:
  set BRIDGE_ORACLE_SECRET=your_secret
  set ABS_API_URL=http://127.0.0.1:8080
  python scripts/bridge_relayer.py --once
  python scripts/bridge_relayer.py --interval 30
  python scripts/bridge_relayer.py --once --watch-l1
  set ETH_RPC_URL=https://...
  set BRIDGE_L1_QUEUE_PATH=data/bridge_l1_queue.json
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

from bridge.l1_rpc import (
    chain_rpc_url,
    is_tx_confirmed,
    load_l1_queue,
    min_confirmations,
    save_l1_queue,
)
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


def process_l1_queue(
    base: str,
    secret: str,
    queue_path: str,
    dry_run: bool = False,
) -> int:
    """Watch L1 RPC for queued outbound/incoming bridge proofs."""
    queue = load_l1_queue(queue_path)
    outbound = queue.get("outbound", [])
    incoming = queue.get("incoming", [])
    if not outbound and not incoming:
        print("L1 queue empty")
        return 0

    need = min_confirmations()
    processed = 0
    remaining_out = []
    for item in outbound:
        l1_tx = item.get("l1_tx_hash", "")
        abs_tx = item.get("abs_tx_hash", item.get("tx_hash", ""))
        chain = item.get("chain", item.get("to_chain", "ethereum"))
        rpc = item.get("rpc_url") or chain_rpc_url(chain)
        if not l1_tx or not abs_tx:
            remaining_out.append(item)
            continue
        if not is_tx_confirmed(rpc, l1_tx, need):
            print(f"L1 outbound wait: {l1_tx[:18]}… conf<{need} chain={chain}")
            remaining_out.append(item)
            continue
        print(f"L1 outbound ready: {l1_tx[:18]}… -> confirm {abs_tx[:18]}…")
        if dry_run:
            processed += 1
            continue
        result = _oracle_post(base, "/bridge/oracle/confirm-lock", {"tx_hash": abs_tx}, secret)
        if result.get("confirmed") or result.get("success"):
            processed += 1
            print(f"  OK outbound: {result}")
        else:
            print(f"  FAIL outbound: {result}")
            remaining_out.append(item)

    remaining_in = []
    for item in incoming:
        l1_tx = item.get("l1_tx_hash", item.get("tx_hash", ""))
        recipient = item.get("recipient", item.get("to_address", ""))
        amount = float(item.get("amount", 0))
        from_chain = item.get("from_chain", item.get("source_chain", "ethereum"))
        tx_id = item.get("tx_id", item.get("abs_tx_hash", l1_tx))
        rpc = item.get("rpc_url") or chain_rpc_url(from_chain)
        if not l1_tx or not recipient or amount <= 0:
            remaining_in.append(item)
            continue
        if not is_tx_confirmed(rpc, l1_tx, need):
            print(f"L1 incoming wait: {l1_tx[:18]}… conf<{need} chain={from_chain}")
            remaining_in.append(item)
            continue
        print(f"L1 incoming ready: {l1_tx[:18]}… -> credit {recipient[:18]}… {amount}")
        if dry_run:
            processed += 1
            continue
        payload = {
            "tx_id": tx_id,
            "tx_hash": l1_tx,
            "recipient": recipient,
            "amount": amount,
            "from_chain": from_chain,
        }
        result = _oracle_post(base, "/bridge/oracle/incoming", payload, secret)
        if result.get("confirmed") or result.get("success"):
            processed += 1
            print(f"  OK incoming: {result}")
        else:
            print(f"  FAIL incoming: {result}")
            remaining_in.append(item)

    if not dry_run:
        save_l1_queue(queue_path, {"outbound": remaining_out, "incoming": remaining_in})
    return processed


def main() -> int:
    parser = argparse.ArgumentParser(description="ABS bridge relayer (oracle HMAC + optional L1 watch)")
    parser.add_argument("--api", default=os.getenv("ABS_API_URL", "http://127.0.0.1:8080"))
    parser.add_argument("--secret", default=os.getenv("BRIDGE_ORACLE_SECRET", ""))
    parser.add_argument("--interval", type=int, default=0, help="Poll interval sec (0 = once)")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--watch-l1",
        action="store_true",
        help="Also poll BRIDGE_L1_QUEUE_PATH items against L1 RPC (ETH_RPC_URL, etc.)",
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

    interval = 0 if args.once else (args.interval or 0)
    while True:
        try:
            st = _get(f"{args.api}/status")
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
