#!/usr/bin/env python3
"""Sync WALLET_PRIVATE_KEY from local .env into data/wallet.json (never reads .txt files)."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(ROOT, ".env")
ENV_EXAMPLE = os.path.join(ROOT, ".env.example")
WALLET_PATH = os.path.join(ROOT, "data", "wallet.json")


def _load_env_file(path: str) -> dict:
    out = {}
    if not os.path.isfile(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            out[key.strip()] = val.strip()
    return out


def _ensure_env_exists() -> bool:
    if os.path.isfile(ENV_PATH):
        return True
    if os.path.isfile(ENV_EXAMPLE):
        with open(ENV_EXAMPLE, encoding="utf-8") as src, open(ENV_PATH, "w", encoding="utf-8") as dst:
            dst.write(src.read())
        print(f"Created {ENV_PATH} from .env.example — fill secrets locally, then re-run.")
        return False
    print("Missing .env and .env.example")
    return False


def _update_wallet(private_key_hex: str) -> bool:
    if not os.path.isfile(WALLET_PATH):
        print(f"wallet.json not found: {WALLET_PATH}")
        return False
    sys.path.insert(0, ROOT)
    from crypto.wallet import Wallet

    with open(WALLET_PATH, encoding="utf-8") as f:
        data = json.load(f)
    expected_addr = (data.get("address") or "").lower()
    expected_pub = (data.get("public_key") or "").lower()
    w = Wallet.from_private_key(private_key_hex)
    if expected_pub and w.public_key.lower() != expected_pub:
        return False
    if expected_addr and w.address.lower() != expected_addr:
        return False
    data["private_key"] = private_key_hex
    data["address"] = w.address
    data["public_key"] = w.public_key
    with open(WALLET_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    return True


def main() -> int:
    if not _ensure_env_exists():
        return 0
    env = _load_env_file(ENV_PATH)
    pk = (env.get("WALLET_PRIVATE_KEY") or "").strip()
    if not pk:
        print("WALLET_PRIVATE_KEY empty in .env — add your 64-hex key locally.")
        print("Other secrets (Telegram, API) are read by main.py from .env at runtime.")
        return 0
    if len(pk) != 64:
        print("WALLET_PRIVATE_KEY must be 64 hex characters")
        return 1
    if _update_wallet(pk):
        print("Synced wallet.json from .env (address verified)")
    else:
        print(
            "OK: WALLET_PRIVATE_KEY is operational wallet (not founder in wallet.json). "
            "main.py uses it for mining/signing; founder address stays watch-only in wallet.json."
        )
    print("Restart: .\\scripts\\stop_node.ps1 then .\\scripts\\start_node.ps1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
