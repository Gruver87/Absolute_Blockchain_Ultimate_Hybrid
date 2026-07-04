#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Consistent SQLite clone for running nodes (WAL-safe)."""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys


def clone_sqlite_db(source: str, dest: str) -> None:
    src = os.path.abspath(source)
    dst = os.path.abspath(dest)
    if not os.path.isfile(src):
        raise FileNotFoundError(f"source database not found: {src}")

    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    base = os.path.basename(dst)
    dst_dir = os.path.dirname(dst) or "."
    for suffix in ("", "-wal", "-shm"):
        path = os.path.join(dst_dir, base + suffix) if suffix else dst
        if os.path.exists(path):
            os.remove(path)

    src_uri = f"file:{src}?mode=ro"
    src_conn = sqlite3.connect(src_uri, uri=True)
    dst_conn = sqlite3.connect(dst)
    try:
        src_conn.backup(dst_conn)
        dst_conn.execute("PRAGMA journal_mode=WAL")
        dst_conn.execute("PRAGMA wal_checkpoint(FULL)")
        dst_conn.commit()
    finally:
        src_conn.close()
        dst_conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Clone node blockchain.db (online-safe)")
    parser.add_argument("--source", required=True, help="Path to source blockchain.db")
    parser.add_argument("--dest", required=True, help="Path to destination blockchain.db")
    args = parser.parse_args()
    try:
        clone_sqlite_db(args.source, args.dest)
    except Exception as exc:
        print(f"clone_node_db failed: {exc}", file=sys.stderr)
        return 1
    print(f"Cloned {args.source} -> {args.dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
