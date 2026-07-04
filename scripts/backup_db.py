#!/usr/bin/env python3
"""Online SQLite backup for node chain database."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.config import Config  # noqa: E402
from storage.database import Database  # noqa: E402


def backup_database(source: str, dest: str) -> bool:
    source = os.path.abspath(source)
    dest = os.path.abspath(dest)
    if not os.path.isfile(source):
        raise FileNotFoundError(f"source database not found: {source}")
    cfg = Config()
    cfg.db_path = source
    db = Database(source)
    db.initialize()
    try:
        return bool(db.backup_to(dest))
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup blockchain SQLite DB (online-safe)")
    parser.add_argument(
        "--source",
        default="data/blockchain.db",
        help="Source chain.db path (default: data/blockchain.db)",
    )
    parser.add_argument("--dest", required=True, help="Destination backup file path")
    args = parser.parse_args()
    try:
        ok = backup_database(args.source, args.dest)
    except Exception as exc:
        print(f"backup_db failed: {exc}", file=sys.stderr)
        return 1
    if not ok:
        print("backup_db failed: backup_to returned false", file=sys.stderr)
        return 1
    print(f"Backed up {args.source} -> {args.dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
