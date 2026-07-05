#!/usr/bin/env python3
"""DR drill: RocksDB chainstore backup + restore roundtrip."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run_rocks_drill() -> int:
    try:
        import abs_native  # type: ignore

        if not hasattr(abs_native, "RocksEngine"):
            print("SKIP: abs_native.RocksEngine not built")
            return 0
    except Exception as exc:
        print(f"SKIP: abs_native unavailable ({exc})")
        return 0

    from core.blockchain import Blockchain
    from kernel.event_bus import EventBus
    from runtime.config import Config
    from storage.chain_backup import backup_chainstore, restore_chainstore, verify_chain_tip
    from storage.factory import open_database

    tmp = tempfile.mkdtemp(prefix="abs_rocks_dr_")
    data_root = os.path.join(tmp, "node_data")
    os.makedirs(data_root, exist_ok=True)

    cfg = Config()
    cfg.db_path = os.path.join(data_root, "chainstore")
    cfg.db_engine = "rocksdb"
    cfg.rocksdb_sync = "FULL"
    cfg.chain_id = 778888

    db = open_database(cfg)
    db.initialize()
    Blockchain(cfg, db, EventBus())
    tip_before = int(db.get_chain_tip() or 0)
    db.close()

    backup_root = os.path.join(tmp, "backup")
    manifest = backup_chainstore(data_root, backup_root)
    if manifest.get("engine") != "rocksdb":
        print("FAIL: expected rocksdb backup", file=sys.stderr)
        return 1

    restore_dir = os.path.join(tmp, "restored")
    restore_chainstore(backup_root, restore_dir, force=True)
    rc = verify_chain_tip(restore_dir, tip_before)
    if rc != 0:
        print(f"FAIL: verify rc={rc}", file=sys.stderr)
        return rc
    print(f"OK: rocks backup drill tip={tip_before}")
    return 0


def main() -> int:
    return run_rocks_drill()


if __name__ == "__main__":
    raise SystemExit(main())
