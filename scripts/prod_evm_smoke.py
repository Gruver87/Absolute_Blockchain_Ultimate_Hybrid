#!/usr/bin/env python3
"""Live prod mesh: EVM deploy + storage persist across HTTP/RPC ports."""
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
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from verify_p2p_ci import (  # noqa: E402
    _admin_token,
    _api,
    _post_json,
    _probe_health,
)

# Minimal constructor: store 1 in slot 0, return runtime code.
DEPLOY_BYTECODE = "600160005260206000f3"
STORAGE_SLOT = "0x0"


def _rpc(url: str, method: str, params: list, api_key: str, timeout: float = 15):
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    data = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode())
    if body.get("error"):
        raise RuntimeError(body["error"])
    return body.get("result")


def _rpc_api_key() -> str:
    raw = os.environ.get("RPC_API_KEYS", "").strip()
    if not raw:
        return ""
    return raw.split(",")[0].strip()


def _wallet_address(wallet_path: str) -> str:
    from crypto.wallet import Wallet

    return Wallet.import_wallet(wallet_path).address


def _ensure_deployer_balance(http_url: str, deployer: str, min_balance: float = 5.0) -> None:
    info = _api(f"{http_url}/address/{deployer}")
    balance = float(info.get("balance", 0) or 0)
    if balance < min_balance:
        raise RuntimeError(
            f"deployer balance too low ({balance}); need >={min_balance} ABS on {http_url}"
        )


def _deploy_contract(http_url: str, deployer: str, salt: str) -> str:
    _admin_token(http_url)
    result = _post_json(
        http_url,
        "/contract/deploy",
        {
            "from": deployer,
            "bytecode": DEPLOY_BYTECODE,
            "salt": salt,
            "value": 0,
        },
        timeout=30,
    )
    if not result.get("success"):
        raise RuntimeError(f"deploy failed: {result.get('error') or result}")
    contract = str(result.get("return_value") or "").strip()
    if not contract:
        raise RuntimeError("deploy returned no contract address")
    return contract


def _storage_ok(storage_hex: str) -> bool:
    try:
        return int(str(storage_hex), 16) == 1
    except ValueError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Prod mesh EVM deploy + RPC storage smoke")
    parser.add_argument("--url1", default="http://127.0.0.1:18180")
    parser.add_argument("--url2", default="http://127.0.0.1:18181")
    parser.add_argument("--url3", default="http://127.0.0.1:18182")
    parser.add_argument("--rpc1", default="http://127.0.0.1:18546")
    parser.add_argument("--rpc2", default="http://127.0.0.1:18547")
    parser.add_argument("--rpc3", default="http://127.0.0.1:18548")
    parser.add_argument(
        "--wallet",
        default="",
        help="Deployer wallet JSON (default: data/prod_mesh/wallets/validator-1.wallet.json)",
    )
    args = parser.parse_args()

    wallet = (args.wallet or "").strip()
    if not wallet:
        wallet = os.path.join(ROOT, "data", "prod_mesh", "wallets", "validator-1.wallet.json")
    if not os.path.isfile(wallet):
        print(f"FAIL: wallet not found: {wallet}")
        return 1

    http_urls = [args.url1, args.url2, args.url3]
    rpc_urls = [args.rpc1, args.rpc2, args.rpc3]
    api_key = _rpc_api_key()
    if not api_key:
        print("FAIL: set RPC_API_KEYS env (prod mesh .env)")
        return 1

    for i, url in enumerate(http_urls, start=1):
        if not _probe_health(url):
            print(f"FAIL: node{i} HTTP not reachable at {url}")
            return 1

    try:
        deployer = _wallet_address(wallet)
    except Exception as exc:
        print(f"FAIL: wallet load: {exc}")
        return 1

    status = _api(f"{args.url1}/status")
    if str(status.get("deployment_mode", "")).lower() != "prod":
        print(f"FAIL: expected deployment_mode=prod, got {status.get('deployment_mode')!r}")
        return 1

    print(f"Prod EVM smoke: deployer={deployer} http={args.url1}")
    try:
        _ensure_deployer_balance(args.url1, deployer)
        salt = f"prod-evm-smoke-{time.time_ns()}"
        contract = _deploy_contract(args.url1, deployer, salt)
        print(f"  deployed contract={contract} salt={salt}")
        time.sleep(2)
    except (urllib.error.URLError, RuntimeError, OSError) as exc:
        print(f"FAIL: deploy: {exc}")
        return 1

    # eth_getCode on leader RPC
    try:
        code = _rpc(rpc_urls[0], "eth_getCode", [contract, "latest"], api_key)
        if not code or code in ("0x", "0x0"):
            print(f"FAIL: eth_getCode empty on {rpc_urls[0]}")
            return 1
        print(f"  eth_getCode len={len(code)}")
    except Exception as exc:
        print(f"FAIL: eth_getCode: {exc}")
        return 1

    # storage visible on all RPC peers
    for i, rpc_url in enumerate(rpc_urls, start=1):
        try:
            storage = _rpc(rpc_url, "eth_getStorageAt", [contract, STORAGE_SLOT, "latest"], api_key)
            if not _storage_ok(str(storage)):
                print(f"FAIL: node{i} storage={storage!r} (expected slot0=1)")
                return 1
            print(f"  OK: node{i} eth_getStorageAt slot0={storage}")
        except Exception as exc:
            print(f"FAIL: node{i} eth_getStorageAt: {exc}")
            return 1

    # HTTP contract call (static)
    try:
        _admin_token(args.url1)
        call = _post_json(
            args.url1,
            "/contract/call",
            {"from": deployer, "to": contract, "data": "0x", "value": 0},
            timeout=30,
        )
        if not call.get("success", True) and call.get("error"):
            print(f"WARN: contract/call: {call.get('error')}")
        else:
            print("  OK: /contract/call completed")
    except Exception as exc:
        print(f"WARN: /contract/call: {exc}")

    print("OK: prod EVM deploy + storage on all RPC nodes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
