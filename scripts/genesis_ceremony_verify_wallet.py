#!/usr/bin/env python3
"""Verify a validator wallet file matches a manifest row."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.ceremony_keygen import verify_wallet_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify wallet ↔ manifest validator binding")
    parser.add_argument("--wallet", required=True, help="Path to wallet.json")
    parser.add_argument("--manifest", required=True, help="Validator manifest JSON")
    parser.add_argument("--index", type=int, required=True, help="Validator index in manifest")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    wallet = Path(args.wallet)
    manifest = Path(args.manifest)
    if not wallet.is_absolute():
        wallet = ROOT / wallet
    if not manifest.is_absolute():
        manifest = ROOT / manifest

    ok, reason = verify_wallet_file(str(wallet), str(manifest), args.index)
    payload = {"ok": ok, "index": args.index, "reason": reason}
    if args.json:
        print(json.dumps(payload, indent=2))
    elif ok:
        print(f"OK: wallet matches manifest index={args.index}")
    else:
        print(f"FAIL: {reason}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
