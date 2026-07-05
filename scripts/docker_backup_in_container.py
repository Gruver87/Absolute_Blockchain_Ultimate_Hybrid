#!/usr/bin/env python3
"""In-container RocksDB checkpoint backup (stdin pipe, no repo scripts required)."""

from __future__ import annotations

import json
import os
import shutil
import sys
import time


def main() -> int:
    data_dir = os.environ.get("DATA_DIR", "/app/data").strip()
    dest_root = os.environ.get("BACKUP_DEST", "").strip()
    if not dest_root:
        print("FAIL: set BACKUP_DEST", file=sys.stderr)
        return 1

    chainstore = os.path.join(data_dir, "chainstore")
    if not os.path.isdir(chainstore):
        print(f"FAIL: missing {chainstore}", file=sys.stderr)
        return 1

    try:
        import abs_native  # type: ignore
    except Exception as exc:
        print(f"FAIL: abs_native unavailable ({exc})", file=sys.stderr)
        return 1

    out_chain = os.path.join(dest_root, "chainstore")
    if os.path.isdir(dest_root):
        shutil.rmtree(dest_root)
    os.makedirs(dest_root, exist_ok=True)

    engine = abs_native.RocksEngine(
        chainstore,
        create_if_missing=False,
        sync_writes=False,
    )
    engine.checkpoint(out_chain)

    aux_src = os.path.join(chainstore, "aux.db")
    if os.path.isfile(aux_src):
        shutil.copy2(aux_src, os.path.join(out_chain, "aux.db"))

    tip = 0
    try:
        from runtime.config import Config
        from storage.factory import open_database

        cfg = Config()
        cfg.db_path = chainstore
        cfg.db_engine = "rocksdb"
        cfg.rocksdb_sync = "FULL"
        db = open_database(cfg)
        db.initialize()
        try:
            tip = int(db.get_chain_tip() or 0)
        finally:
            db.close()
    except Exception:
        pass

    manifest = {
        "engine": "rocksdb",
        "layout": "nested",
        "source": data_dir,
        "created_at": int(time.time()),
        "chain_tip": tip,
        "files": ["chainstore/"],
    }
    if os.path.isfile(os.path.join(out_chain, "aux.db")):
        manifest["files"].append("chainstore/aux.db")

    manifest_path = os.path.join(dest_root, "backup_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    print(f"OK: engine=rocksdb tip={tip} dest={dest_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
