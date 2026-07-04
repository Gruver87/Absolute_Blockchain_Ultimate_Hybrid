#!/usr/bin/env python3
"""PyO3 native crypto helper for bridge/CI pipelines (keccak + ecrecover probes)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crypto import native


def cmd_keccak(args: argparse.Namespace) -> int:
    data = bytes.fromhex(args.hex.replace("0x", ""))
    digest = native.keccak256_digest(data)
    print("0x" + digest.hex())
    return 0


def cmd_recover(args: argparse.Namespace) -> int:
    msg = bytes.fromhex(args.message.replace("0x", ""))
    sig = bytes.fromhex(args.signature.replace("0x", ""))
    addr = native.recover_eth_address_keccak(msg, sig)
    print(addr)
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    print(json.dumps({
        "native_available": native.native_available(),
    }))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="abs_native PyO3 bridge helper")
    sub = parser.add_subparsers(dest="command", required=True)

    p_keccak = sub.add_parser("keccak", help="Keccak-256 hex digest")
    p_keccak.add_argument("hex", help="input hex (optional 0x prefix)")
    p_keccak.set_defaults(func=cmd_keccak)

    p_recover = sub.add_parser("recover", help="ecrecover secp256k1 address")
    p_recover.add_argument("message", help="32-byte message hash hex")
    p_recover.add_argument("signature", help="65-byte signature hex")
    p_recover.set_defaults(func=cmd_recover)

    p_status = sub.add_parser("status", help="native module availability")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
