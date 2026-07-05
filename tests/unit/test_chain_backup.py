#!/usr/bin/env python3
"""Chain backup/restore unit tests."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    import abs_native  # type: ignore

    HAS_ROCKS = hasattr(abs_native, "RocksEngine")
except Exception:
    HAS_ROCKS = False


def test_detect_engine_sqlite(tmp_path):
    from storage.chain_backup import detect_engine

    db = tmp_path / "blockchain.db"
    db.write_text("")
    assert detect_engine(str(tmp_path)) == "sqlite"


def test_detect_engine_rocksdb(tmp_path):
    from storage.chain_backup import detect_engine

    (tmp_path / "chainstore").mkdir()
    assert detect_engine(str(tmp_path)) == "rocksdb"


@pytest.mark.skipif(not HAS_ROCKS, reason="abs_native.RocksEngine not built")
def test_backup_restore_roundtrip(tmp_path):
    from core.blockchain import Blockchain
    from kernel.event_bus import EventBus
    from runtime.config import Config
    from storage.chain_backup import backup_chainstore, restore_chainstore, verify_chain_tip
    from storage.factory import open_database

    data_root = tmp_path / "node_data"
    data_root.mkdir()
    cfg = Config()
    cfg.db_path = str(data_root / "chainstore")
    cfg.db_engine = "rocksdb"
    cfg.rocksdb_sync = "FULL"
    cfg.chain_id = 778888

    db = open_database(cfg)
    db.initialize()
    Blockchain(cfg, db, EventBus())
    tip = int(db.get_chain_tip() or 0)
    db.close()

    backup_dir = tmp_path / "backup"
    manifest = backup_chainstore(str(data_root), str(backup_dir))
    assert manifest["engine"] == "rocksdb"
    assert manifest["layout"] == "nested"

    restore_dir = tmp_path / "restored"
    restore_chainstore(str(backup_dir), str(restore_dir), force=True)
    assert verify_chain_tip(str(restore_dir), tip) == 0
