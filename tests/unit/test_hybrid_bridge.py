#!/usr/bin/env python3
"""HybridDatabase bridge routing and aux→Rocks migration."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    import abs_native  # type: ignore

    HAS_ROCKS = hasattr(abs_native, "RocksEngine")
except Exception:
    HAS_ROCKS = False

pytestmark = pytest.mark.skipif(not HAS_ROCKS, reason="abs_native.RocksEngine not built")


class _Cfg:
    def __init__(self, path: str):
        self.db_path = path
        self.rocksdb_sync = "FULL"
        self.sqlite_synchronous = "NORMAL"


def test_hybrid_bridge_routes_to_core(tmp_path):
    from storage import keycodec as kc
    from storage.hybrid_database import HybridDatabase

    path = str(tmp_path / "chainstore")
    db = HybridDatabase(_Cfg(path))
    db.initialize()
    db.save_bridge_lock("0xalice", "ethereum", "0xrecipient", 5.0, "0x" + "22" * 32)
    locks = db.get_bridge_locks()
    assert len(locks) == 1
    assert locks[0]["from_addr"] == "0xalice"
    raw = db._core._raw_get(kc.key_bridge_lock("0x" + "22" * 32))
    assert raw is not None
    db.close()


def test_hybrid_migrates_aux_bridge_locks(tmp_path):
    from storage import keycodec as kc
    from storage.hybrid_database import HybridDatabase

    path = str(tmp_path / "chainstore")
    db = HybridDatabase(_Cfg(path))
    db._aux.save_bridge_lock("0xfrom", "bsc", "0xto", 3.0, "0x" + "33" * 32)
    db._aux.confirm_bridge_lock("0x" + "33" * 32)
    db.initialize()
    locks = db.get_bridge_locks()
    assert len(locks) == 1
    assert locks[0]["status"] == "confirmed"
    assert db._core._raw_get(kc.key_bridge_lock("0x" + "33" * 32)) is not None
    assert db.get_meta("aux_bridge_migrated_v1") is True
    db.close()
