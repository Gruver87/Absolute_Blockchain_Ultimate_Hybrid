#!/usr/bin/env python3
"""Live prod mesh: signed transfer + mempool propagation (no auto_sign)."""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from verify_p2p_ci import (
    _api,
    _probe_health,
    _restore_p2p_mesh,
    _verify_tx_propagation_multi,
    _wait_peer_counts,
    _wait_topology_healthy,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prod mesh signed tx smoke")
    parser.add_argument("--url1", default="http://127.0.0.1:18180")
    parser.add_argument("--url2", default="http://127.0.0.1:18181")
    parser.add_argument("--url3", default="http://127.0.0.1:18182")
    parser.add_argument(
        "--wallet",
        default="",
        help="Signer wallet JSON (default: data/prod_mesh/wallets/validator-1.wallet.json)",
    )
    args = parser.parse_args()

    wallet = (args.wallet or "").strip()
    if not wallet:
        wallet = os.path.join(ROOT, "data", "prod_mesh", "wallets", "validator-1.wallet.json")
    if not os.path.isfile(wallet):
        print(f"FAIL: wallet not found: {wallet}")
        return 1

    urls = [args.url1, args.url2, args.url3]
    for i, url in enumerate(urls, start=1):
        if not _probe_health(url):
            print(f"FAIL: node{i} not reachable at {url}")
            return 1

    os.environ["PROD_SMOKE_WALLET_PATH"] = wallet
    print(f"Prod signed-tx smoke: {args.url1} wallet={wallet}")

    _restore_p2p_mesh(urls, expected_peers=2)
    if not _wait_topology_healthy(args.url1, expected_peers=2, timeout=120):
        _wait_peer_counts(
            urls, leader_url=args.url1, leader_min_peers=2, follower_min_peers=1, timeout=60
        )

    for _ in range(40):
        try:
            h = int(_api(f"{args.url1}/status").get("height", 0) or 0)
            if h >= 2:
                break
        except Exception:
            pass
        time.sleep(3)

    try:
        s1 = _api(f"{args.url1}/status")
    except Exception as exc:
        print(f"FAIL: cannot read status: {exc}")
        return 1

    if str(s1.get("deployment_mode", "")).lower() != "prod":
        print(f"FAIL: expected deployment_mode=prod, got {s1.get('deployment_mode')!r}")
        return 1

    ok = _verify_tx_propagation_multi(args.url1, urls[1:], s1)
    if not ok:
        print("FAIL: prod signed tx propagation")
        return 1

    print("OK: prod signed tx propagation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
