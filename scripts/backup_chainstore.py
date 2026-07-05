#!/usr/bin/env python3
"""Backup RocksDB chainstore or legacy SQLite chain DB."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from storage.chain_backup import backup_chainstore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup chain data")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--dest", default="")
    args = parser.parse_args()
    ts = time.strftime("%Y%m%d-%H%M%S")
    dest = args.dest.strip() or os.path.join("backups", f"chain-backup-{ts}")
    try:
        manifest = backup_chainstore(args.data_dir, dest)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        f"OK: backup engine={manifest['engine']} tip={manifest.get('chain_tip', '?')} "
        f"dest={dest}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
