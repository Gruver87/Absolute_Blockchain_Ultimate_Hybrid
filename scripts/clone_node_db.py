#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Consistent chain clone for running nodes (SQLite WAL-safe or RocksDB directory)."""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from storage.chain_clone import clone_chain_data, _clone_sqlite_file  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Clone node chain data (sqlite or rocksdb)")
    parser.add_argument("--source", required=True, help="Source data dir or blockchain.db path")
    parser.add_argument("--dest", required=True, help="Destination data dir or blockchain.db path")
    args = parser.parse_args()
    src = os.path.abspath(args.source)
    dst = os.path.abspath(args.dest)
    try:
        if os.path.isfile(src) and src.endswith(".db"):
            _clone_sqlite_file(src, dst)
            print(f"Cloned sqlite {src} -> {dst}")
            return 0
        engine = clone_chain_data(src, dst)
        print(f"Cloned {engine} chain {src} -> {dst}")
    except Exception as exc:
        print(f"clone_node_db failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
