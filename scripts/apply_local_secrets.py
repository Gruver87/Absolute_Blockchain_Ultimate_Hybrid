#!/usr/bin/env python3
"""Apply local secrets from Desktop commands file into .env and data/wallet.json."""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMANDS = os.path.join(os.path.expanduser("~"), "Desktop", "Absolute_Blockchain_All_Commands_FIXED.txt")
ENV_PATH = os.path.join(ROOT, ".env")
WALLET_PATH = os.path.join(ROOT, "data", "wallet.json")


def _read_text(path: str) -> str:
    if not os.path.isfile(path):
        return ""
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read()


def _parse_commands(text: str) -> dict:
    out = {}
    patterns = {
        "OPENWEATHER_API_KEY": r'OPENWEATHER_API_KEY:\s*"([^"]+)"',
        "WEATHERAPI_KEY": r'WEATHERAPI_KEY:\s*"([^"]+)"',
        "TELEGRAM_BOT_TOKEN": r'TELEGRAM_BOT_TOKEN:\s*"([^"]+)"',
        "WALLET_PRIVATE_KEY": r"Private Key:\s*([0-9a-fA-F]{64})",
    }
    for key, pat in patterns.items():
        m = re.search(pat, text)
        if m:
            out[key] = m.group(1).strip()
    return out


def _update_env(secrets: dict) -> None:
    lines = []
    if os.path.isfile(ENV_PATH):
        with open(ENV_PATH, encoding="utf-8") as f:
            lines = f.read().splitlines()
    keys = {k: v for k, v in secrets.items() if k != "WALLET_PRIVATE_KEY"}
    if secrets.get("WALLET_PRIVATE_KEY"):
        keys["WALLET_PRIVATE_KEY"] = secrets["WALLET_PRIVATE_KEY"]
    present = set()
    new_lines = []
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            k = line.split("=", 1)[0].strip()
            if k in keys:
                new_lines.append(f"{k}={keys[k]}")
                present.add(k)
                continue
        new_lines.append(line)
    for k, v in keys.items():
        if k not in present:
            new_lines.append(f"{k}={v}")
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines) + "\n")


def _update_wallet(private_key_hex: str) -> bool:
    if not os.path.isfile(WALLET_PATH):
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
    text = _read_text(COMMANDS)
    if not text:
        print(f"Commands file not found: {COMMANDS}")
        return 1
    secrets = _parse_commands(text)
    if not secrets:
        print("No secrets parsed from commands file")
        return 1
    _update_env(secrets)
    print(f"Updated: {ENV_PATH}")
    pk = secrets.get("WALLET_PRIVATE_KEY", "")
    if pk:
        if _update_wallet(pk):
            print(f"Updated: {WALLET_PATH} (private_key matched founder wallet)")
        else:
            print(
                "wallet.json: private_key from commands file does NOT match "
                "founder address/public_key — kept address-only; key stored in .env only"
            )
    print("Done. Restart node: .\\scripts\\stop_node.ps1 then .\\scripts\\start_node.ps1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
