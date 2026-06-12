#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Online-бэкап SQLite базы узла (без остановки ноды)."""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.database import Database


def main():
    parser = argparse.ArgumentParser(description="Backup Absolute Blockchain SQLite DB")
    default_db = os.path.join(os.getenv("DATA_DIR", "data"), "blockchain.db")
    parser.add_argument(
        "--db",
        default=default_db,
        help="Path to blockchain.db",
    )
    parser.add_argument(
        "--out-dir",
        default="",
        help="Backup directory (default: <db_dir>/backups)",
    )
    args = parser.parse_args()

    db_path = args.db.replace("\\", "/")
    if db_path.endswith("/blockchain.db") is False and not db_path.endswith("blockchain.db"):
        db_path = os.path.join(db_path, "blockchain.db")

    if not os.path.isfile(db_path):
        print(f"ERROR: database not found: {db_path}")
        sys.exit(1)

    out_dir = args.out_dir or os.path.join(os.path.dirname(db_path) or ".", "backups")
    os.makedirs(out_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(out_dir, f"blockchain_{stamp}.db")

    db = Database(db_path)
    ok = db.backup_to(dest)
    db.close()

    if ok:
        print(f"OK: backup saved to {dest}")
        sys.exit(0)
    print("ERROR: backup failed")
    sys.exit(1)


if __name__ == "__main__":
    main()
