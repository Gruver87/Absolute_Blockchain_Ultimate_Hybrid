#!/usr/bin/env python3
"""Database factory — sqlite (default) or rocksdb hybrid + StoragePort façade."""

from __future__ import annotations

from typing import Any, Union

from storage.database import Database
from storage.ports import StoragePort


def open_database(config: Any) -> Union[Database, Any]:
    engine = (getattr(config, "db_engine", "sqlite") or "sqlite").strip().lower()
    if engine == "rocksdb":
        from storage.hybrid_database import HybridDatabase

        return HybridDatabase(config)
    return Database(
        config.db_path,
        synchronous=getattr(config, "sqlite_synchronous", "NORMAL"),
    )


def open_storage(db: Any, *, repair_on_open: bool = True) -> StoragePort:
    """Wrap a legacy Database / HybridDatabase as ADR 0006 ``StoragePort``.

    Same adapter works for SQLite and Rocks: both expose ``_persist_block_locked``
    and tip APIs. ``repair_on_open`` rewinds orphan tip meta (Rocks tip fence).
    """
    from storage.adapters.rocks_adapter import RocksDBStorageAdapter

    fail_closed = True
    try:
        cfg = getattr(db, "config", None)
        if cfg is not None and hasattr(cfg, "require_native_crypto"):
            fail_closed = bool(getattr(cfg, "require_native_crypto", False)) or str(
                getattr(cfg, "deployment_mode", "dev") or "dev"
            ).lower() in ("prod", "production")
    except Exception:
        fail_closed = True
    return RocksDBStorageAdapter(
        db,
        fail_closed_repair=fail_closed,
        repair_on_open=bool(repair_on_open),
    )
