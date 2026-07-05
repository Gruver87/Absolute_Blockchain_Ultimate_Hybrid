#!/usr/bin/env python3
"""Restore chain data from backup_chainstore.py output."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from storage.chain_backup import restore_chainstore, verify_chain_tip  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore chain backup")
    parser.add_argument("--backup-dir", required=True)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    try:
        manifest = restore_chainstore(
            args.backup_dir, args.data_dir, force=args.force
        )
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"OK: restored engine={manifest.get('engine')} -> {args.data_dir}")
    if args.verify:
        rc = verify_chain_tip(args.data_dir, manifest.get("chain_tip"))
        if rc == 0:
            print(f"OK: verify tip={manifest.get('chain_tip')}")
        else:
            print(f"FAIL: verify rc={rc}", file=sys.stderr)
        return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
