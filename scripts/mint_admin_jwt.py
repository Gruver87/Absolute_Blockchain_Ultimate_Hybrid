#!/usr/bin/env python3
"""Mint an admin JWT from JWT_SECRET (prod: /auth/token is disabled)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Mint Absolute admin JWT from JWT_SECRET")
    parser.add_argument("--address", default="ops-admin", help="JWT address claim")
    parser.add_argument("--hours", type=float, default=24.0, help="Token lifetime hours")
    parser.add_argument(
        "--role",
        default="admin",
        choices=("admin", "user"),
        help="JWT role (admin required for protected POSTs)",
    )
    parser.add_argument("--secret", default="", help="Override JWT_SECRET (prefer env)")
    args = parser.parse_args()

    secret = (args.secret or os.environ.get("JWT_SECRET", "")).strip()
    if not secret:
        print("FAIL: set JWT_SECRET (or --secret)", file=sys.stderr)
        return 1

    os.environ["JWT_SECRET"] = secret
    # Re-bind module secret after env set
    import importlib
    import middleware.jwt_auth as jwt_mod

    importlib.reload(jwt_mod)
    jwt_mod.jwt_auth.secret_key = secret
    jwt_mod.jwt_auth.expiration_hours = float(args.hours)

    try:
        token = jwt_mod.jwt_auth.generate_token(args.address, role=args.role)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
