#!/usr/bin/env python3
"""Database factory — sqlite (default) or rocksdb hybrid."""

from __future__ import annotations

from typing import Any, Union

from storage.database import Database


def open_database(config: Any) -> Union[Database, Any]:
    engine = (getattr(config, "db_engine", "sqlite") or "sqlite").strip().lower()
    if engine == "rocksdb":
        from storage.hybrid_database import HybridDatabase

        return HybridDatabase(config)
    return Database(
        config.db_path,
        synchronous=getattr(config, "sqlite_synchronous", "NORMAL"),
    )
