#!/usr/bin/env python3
"""
Migrate legacy SQLite chain DB to RocksDB chainstore.

Usage:
  python scripts/migrate_sqlite_to_rocks.py --source data/blockchain.db --dest data/chainstore
  python scripts/migrate_sqlite_to_rocks.py --source data/blockchain.db --dest data/chainstore --verify
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from execution.state_root import compute_db_state_root  # noqa: E402
from storage import keycodec as kc  # noqa: E402
from storage.database import Database  # noqa: E402
from storage.rocks_store import RocksChainStore  # noqa: E402


def _load_sqlite_rows(conn, table: str) -> list[dict]:
    rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    return [dict(r) for r in rows]


def migrate(source_db: str, dest_chainstore: str, *, sync: str = "FULL") -> dict:
    src = Database(os.path.abspath(source_db))
    src.initialize()
    rocks = RocksChainStore(os.path.abspath(dest_chainstore), synchronous=sync)
    rocks.initialize()

    stats = {
        "blocks": 0,
        "accounts": 0,
        "validators": 0,
        "transactions": 0,
        "receipts": 0,
        "burn_rows": 0,
        "meta_keys": 0,
        "proposer_audit": 0,
        "bridge_locks": 0,
        "bridge_credits": 0,
    }

    try:
        with rocks.atomic():
            for row in _load_sqlite_rows(src.conn, "blocks"):
                block = json.loads(row.get("data", "{}"))
                rocks._insert_block(block)
                stats["blocks"] += 1

            for row in _load_sqlite_rows(src.conn, "accounts"):
                rocks._save_account_row(
                    {
                        "address": row.get("address", ""),
                        "balance": float(row.get("balance", 0.0) or 0.0),
                        "nonce": int(row.get("nonce", 0) or 0),
                        "code": row.get("code"),
                        "storage": row.get("storage"),
                    }
                )
                stats["accounts"] += 1

            for row in _load_sqlite_rows(src.conn, "validators"):
                rocks.save_validator(row.get("address", ""), float(row.get("stake", 0.0) or 0.0))
                stats["validators"] += 1

            for row in _load_sqlite_rows(src.conn, "transactions"):
                rocks._insert_transaction(row)
                stats["transactions"] += 1

            for row in _load_sqlite_rows(src.conn, "tx_receipts"):
                rocks._raw_put(
                    kc.P_TX_RECEIPT + kc.key_tx(row["tx_hash"])[1:],
                    json.dumps(
                        {
                            "tx_hash": row.get("tx_hash", ""),
                            "block_height": int(row.get("block_height", 0) or 0),
                            "block_hash": row.get("block_hash", ""),
                            "from_addr": row.get("from_addr", ""),
                            "to_addr": row.get("to_addr", ""),
                            "value": row.get("value", 0.0),
                            "fee": row.get("fee", 0.0),
                            "burned": row.get("burned", 0.0),
                            "gas_used": row.get("gas_used", 0),
                            "status": row.get("status", 1),
                            "created_at": int(row.get("created_at", 0) or 0),
                        }
                    ).encode("utf-8"),
                )
                stats["receipts"] += 1

            for row in _load_sqlite_rows(src.conn, "burn_stats"):
                rocks._raw_put(
                    kc.key_burn(int(row.get("block_height", 0) or 0)),
                    json.dumps(row).encode("utf-8"),
                )
                stats["burn_rows"] += 1

            for row in _load_sqlite_rows(src.conn, "block_proposer_audit"):
                rocks._raw_put(
                    kc.key_proposer_audit(int(row.get("height", 0) or 0)),
                    json.dumps(
                        {
                            "height": row.get("height", 0),
                            "block_hash": row.get("block_hash", ""),
                            "proposer": row.get("proposer", ""),
                            "tx_count": row.get("tx_count", 0),
                            "total_burned": row.get("total_burned", 0.0),
                            "block_ts": row.get("block_ts", 0),
                            "recorded_at": row.get("recorded_at", 0),
                        }
                    ).encode("utf-8"),
                )
                stats["proposer_audit"] += 1

            for row in _load_sqlite_rows(src.conn, "meta"):
                key = row.get("key", "")
                if not key:
                    continue
                raw = row.get("value", "")
                try:
                    value = json.loads(raw)
                except Exception:
                    value = raw
                rocks._raw_put(
                    kc.key_meta(key),
                    json.dumps(value, ensure_ascii=False).encode("utf-8"),
                )
                stats["meta_keys"] += 1

            for row in _load_sqlite_rows(src.conn, "bridge_locks"):
                tx_hash = row.get("tx_hash", "") or ""
                if not tx_hash:
                    continue
                rocks._raw_put(
                    kc.key_bridge_lock(tx_hash),
                    json.dumps(dict(row), ensure_ascii=False).encode("utf-8"),
                )
                stats["bridge_locks"] += 1

            for row in _load_sqlite_rows(src.conn, "bridge_credits"):
                credit_key = row.get("credit_key", "") or ""
                if not credit_key:
                    continue
                rocks._raw_put(
                    kc.key_bridge_credit(credit_key),
                    json.dumps(dict(row), ensure_ascii=False).encode("utf-8"),
                )
                stats["bridge_credits"] += 1

        stats["source_tip"] = int(src.get_chain_tip() or 0)
        stats["dest_tip"] = int(rocks.get_chain_tip() or 0)
        stats["source_state_root"] = src.compute_state_root()
        stats["dest_state_root"] = rocks.compute_state_root()
        stats["source_total_burned"] = float(src.get_total_burned() or 0.0)
        stats["dest_total_burned"] = float(rocks.get_total_burned() or 0.0)
        return stats
    finally:
        src.close()
        rocks.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate SQLite chain DB to RocksDB chainstore")
    parser.add_argument("--source", required=True, help="Path to blockchain.db")
    parser.add_argument("--dest", required=True, help="Destination chainstore directory")
    parser.add_argument("--sync", default="FULL", help="RocksDB sync mode (FULL|NORMAL)")
    parser.add_argument("--verify", action="store_true", help="Fail if tip/state_root mismatch")
    args = parser.parse_args()

    try:
        stats = migrate(args.source, args.dest, sync=args.sync)
    except Exception as exc:
        print(f"migrate_sqlite_to_rocks failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(stats, indent=2))
    if args.verify:
        if stats["source_tip"] != stats["dest_tip"]:
            print("VERIFY FAIL: tip mismatch", file=sys.stderr)
            return 2
        if stats["source_state_root"] != stats["dest_state_root"]:
            print("VERIFY FAIL: state_root mismatch", file=sys.stderr)
            return 3
        if abs(stats["source_total_burned"] - stats["dest_total_burned"]) > 1e-9:
            print("VERIFY FAIL: burn total mismatch", file=sys.stderr)
            return 4
    print("OK migrate_sqlite_to_rocks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
