#!/usr/bin/env python3
"""Clone chain data between nodes (SQLite file or RocksDB chainstore directory)."""

from __future__ import annotations

import os
import shutil
import sqlite3
from pathlib import Path


def _clone_sqlite_file(source: str, dest: str) -> None:
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


def _clone_rocks_directory(source: str, dest: str) -> None:
    src = Path(source).resolve()
    dst = Path(dest).resolve()
    if not src.is_dir():
        raise FileNotFoundError(f"source chainstore not found: {src}")
    if dst.exists():
        shutil.rmtree(dst)
    try:
        import abs_native  # type: ignore

        if hasattr(abs_native, "RocksEngine"):
            engine = abs_native.RocksEngine(str(src), create_if_missing=False, sync_writes=False)
            engine.checkpoint(str(dst))
            return
    except Exception:
        pass
    shutil.copytree(src, dst)


def clone_chain_data(source_data_dir: str, dest_data_dir: str) -> str:
    """
    Clone leader chain into follower data directory.

    Detects RocksDB chainstore first, then legacy blockchain.db.
    Returns engine label: 'rocksdb' | 'sqlite'.
    """
    src_dir = Path(source_data_dir).resolve()
    dst_dir = Path(dest_data_dir).resolve()
    dst_dir.mkdir(parents=True, exist_ok=True)

    rocks_src = src_dir / "chainstore"
    if rocks_src.is_dir():
        _clone_rocks_directory(str(rocks_src), str(dst_dir / "chainstore"))
        aux_src = rocks_src / "aux.db"
        if aux_src.is_file():
            shutil.copy2(aux_src, dst_dir / "chainstore" / "aux.db")
        return "rocksdb"

    sqlite_src = src_dir / "blockchain.db"
    if sqlite_src.is_file():
        _clone_sqlite_file(str(sqlite_src), str(dst_dir / "blockchain.db"))
        return "sqlite"

    legacy_src = src_dir / "chain.db"
    if legacy_src.is_file():
        _clone_sqlite_file(str(legacy_src), str(dst_dir / "chain.db"))
        return "sqlite"

    raise FileNotFoundError(
        f"no chainstore/, blockchain.db, or chain.db under {src_dir}"
    )
