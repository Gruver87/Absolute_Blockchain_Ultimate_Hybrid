#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RocksDB chain store — hot path (blocks, state, meta) via abs_native RocksEngine.

Reads are lock-free (RocksDB MVCC). Writes are serialized through WriteBatch commits.
"""

from __future__ import annotations

import json
import os
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from storage import keycodec as kc
from storage.database import Database as SqliteDatabase


def _rocks_available() -> bool:
    try:
        import abs_native  # type: ignore

        return hasattr(abs_native, "RocksEngine")
    except Exception:
        return False


class RocksChainStore:
    """Production chain/state store backed by RocksDB (native PyO3)."""

    engine = "rocksdb"

    def __init__(
        self,
        db_path: str = "data/chainstore",
        *,
        synchronous: str = "FULL",
    ):
        if not _rocks_available():
            raise RuntimeError(
                "RocksDB engine requires abs_native with RocksEngine "
                "(rebuild: bash scripts/build_native.sh)"
            )
        import abs_native  # type: ignore

        self.db_path = db_path
        sync = (synchronous or "FULL").upper()
        self.synchronous = sync
        self._write_lock = threading.RLock()
        self._pending_batch: Any | None = None
        os.makedirs(db_path, exist_ok=True)
        self._engine = abs_native.RocksEngine(
            db_path,
            create_if_missing=True,
            sync_writes=sync in ("FULL", "EXTRA", "STRICT"),
        )
        self._schema_version = "rocksdb-chain-v1"
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        existing = self._raw_get(kc.key_meta("schema_version"))
        if existing is None:
            self._raw_put(kc.key_meta("schema_version"), self._schema_version.encode("utf-8"))

    def initialize(self) -> None:
        self._ensure_schema()

    # ── low-level I/O ─────────────────────────────────────────────────────

    def _raw_get(self, key: bytes) -> Optional[bytes]:
        val = self._engine.get(key)
        return bytes(val) if val is not None else None

    def _raw_put(self, key: bytes, value: bytes) -> None:
        if self._pending_batch is not None:
            self._pending_batch.put(key, value)
            return
        self._engine.put(key, value)

    def _raw_delete(self, key: bytes) -> None:
        if self._pending_batch is not None:
            self._pending_batch.delete(key)
            return
        self._engine.delete(key)

    def _scan_prefix(self, prefix: bytes, limit: int = 100_000) -> List[tuple[bytes, bytes]]:
        rows = self._engine.prefix_scan(prefix, limit)
        return [(bytes(k), bytes(v)) for k, v in rows]

    @contextmanager
    def atomic(self):
        import abs_native  # type: ignore

        with self._write_lock:
            batch = abs_native.RocksWriteBatch()
            self._pending_batch = batch
            try:
                yield self
                self._engine.write_batch(batch)
            except Exception:
                raise
            finally:
                self._pending_batch = None

    def close(self) -> None:
        self._engine = None  # type: ignore[assignment]

    def backup_to(self, dest_path: str) -> bool:
        try:
            os.makedirs(dest_path, exist_ok=True)
            self._engine.checkpoint(dest_path)
            return True
        except Exception as exc:
            print(f"[RocksDB] backup_to error: {exc}")
            return False

    # ── meta ──────────────────────────────────────────────────────────────

    def set_meta(self, key: str, value: Any) -> None:
        with self._write_lock:
            self._raw_put(
                kc.key_meta(key),
                json.dumps(value, ensure_ascii=False).encode("utf-8"),
            )

    def get_meta(self, key: str, default: Any = None) -> Any:
        raw = self._raw_get(kc.key_meta(key))
        if raw is None:
            return default
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return raw.decode("utf-8", errors="replace")

    # ── blocks ────────────────────────────────────────────────────────────

    def _insert_block(self, block: Dict) -> None:
        height = int(block.get("height", block.get("number", 0)) or 0)
        block_hash = block.get("hash", block.get("block_hash", "")) or ""
        payload = json.dumps(block, ensure_ascii=False).encode("utf-8")
        self._raw_put(kc.key_block_height(height), payload)
        if block_hash:
            self._raw_put(kc.key_block_hash_to_height(block_hash), kc.pack_u64(height))
        self._insert_proposer_audit(block)

    def _insert_proposer_audit(self, block: Dict) -> None:
        height = int(block.get("height", block.get("number", 0)) or 0)
        audit = {
            "height": height,
            "block_hash": block.get("hash", block.get("block_hash", "")) or "",
            "proposer": SqliteDatabase._normalize_address(
                block.get("miner", block.get("proposer", "genesis")) or "genesis"
            ),
            "tx_count": int(block.get("tx_count", len(block.get("transactions", []))) or 0),
            "total_burned": float(block.get("total_burned", 0.0) or 0.0),
            "block_ts": int(block.get("timestamp", int(time.time())) or 0),
            "recorded_at": int(time.time()),
        }
        self._raw_put(kc.key_proposer_audit(height), json.dumps(audit).encode("utf-8"))

    def save_block(self, block: Dict) -> bool:
        with self._write_lock:
            try:
                self._insert_block(block)
                return True
            except Exception as exc:
                print(f"[RocksDB] save_block error: {exc}")
                return False

    def get_block(self, height: int) -> Optional[Dict]:
        raw = self._raw_get(kc.key_block_height(int(height)))
        return json.loads(raw.decode("utf-8")) if raw else None

    def get_block_by_hash(self, block_hash: str) -> Optional[Dict]:
        raw_h = self._raw_get(kc.key_block_hash_to_height(block_hash))
        if not raw_h:
            return None
        return self.get_block(kc.unpack_u64(raw_h))

    def get_latest_blocks(self, limit: int = 20) -> List[Dict]:
        rows = self._scan_prefix(kc.prefix_block_heights())
        blocks: List[Dict] = []
        for _key, value in sorted(rows, key=lambda kv: kc.unpack_u64(kv[0][1:9]), reverse=True)[:limit]:
            blocks.append(json.loads(value.decode("utf-8")))
        return blocks

    def get_chain_tip(self) -> int:
        rows = self._scan_prefix(kc.prefix_block_heights())
        if not rows:
            return 0
        return max(kc.unpack_u64(key[1:9]) for key, _ in rows)

    def get_last_block(self) -> Optional[Dict]:
        tip = self.get_chain_tip()
        return self.get_block(tip) if tip else None

    # ── accounts / state ──────────────────────────────────────────────────

    def _load_account(self, address: str) -> Dict[str, Any]:
        raw = self._raw_get(kc.key_account(address))
        if not raw:
            return {
                "address": SqliteDatabase._normalize_address(address),
                "balance": 0.0,
                "nonce": 0,
                "code": None,
                "storage": None,
            }
        return json.loads(raw.decode("utf-8"))

    def _save_account_row(self, row: Dict[str, Any]) -> None:
        addr = SqliteDatabase._normalize_address(row.get("address", ""))
        row["address"] = addr
        self._raw_put(kc.key_account(addr), json.dumps(row, ensure_ascii=False).encode("utf-8"))

    def get_balance(self, address: str) -> float:
        return float(self._load_account(address).get("balance", 0.0) or 0.0)

    def get_nonce(self, address: str) -> int:
        return int(self._load_account(address).get("nonce", 0) or 0)

    def get_account(self, address: str) -> Optional[Dict]:
        row = self._load_account(address)
        if row["balance"] == 0.0 and row["nonce"] == 0 and not row.get("code") and not row.get("storage"):
            raw = self._raw_get(kc.key_account(address))
            return None if raw is None else row
        return row

    def _apply_balance_delta(self, address: str, delta: float) -> None:
        row = self._load_account(address)
        row["balance"] = max(0.0, float(row.get("balance", 0.0) or 0.0) + float(delta))
        self._save_account_row(row)

    def balance_delta(self, address: str, delta: float) -> None:
        self._apply_balance_delta(address, delta)

    def update_balance(self, address: str, delta: float) -> float:
        with self._write_lock:
            self._apply_balance_delta(address, delta)
            return self.get_balance(address)

    def set_balance(self, address: str, balance: float) -> None:
        with self._write_lock:
            row = self._load_account(address)
            row["balance"] = float(balance)
            self._save_account_row(row)

    def increment_nonce(self, address: str) -> int:
        with self._write_lock:
            row = self._load_account(address)
            row["nonce"] = int(row.get("nonce", 0) or 0) + 1
            self._save_account_row(row)
            return int(row["nonce"])

    def nonce_increment(self, address: str) -> int:
        row = self._load_account(address)
        row["nonce"] = int(row.get("nonce", 0) or 0) + 1
        self._save_account_row(row)
        return int(row["nonce"])

    def save_account(
        self,
        address: str,
        balance: float = 0.0,
        nonce: int = 0,
        code: str | None = None,
        storage: str | None = None,
    ) -> None:
        with self._write_lock:
            row = self._load_account(address)
            row["balance"] = float(balance)
            row["nonce"] = int(nonce)
            row["code"] = code
            row["storage"] = storage
            self._save_account_row(row)

    def update_account_storage(self, address: str, storage: Dict) -> None:
        with self._write_lock:
            row = self._load_account(address)
            row["storage"] = json.dumps(storage)
            self._save_account_row(row)

    def get_all_accounts(self) -> List[Dict]:
        rows = self._scan_prefix(kc.prefix_accounts())
        out: List[Dict] = []
        for _key, value in rows:
            out.append(json.loads(value.decode("utf-8")))
        return sorted(out, key=lambda r: str(r.get("address", "")))

    def reset_accounts_from_alloc(
        self, alloc: Dict[str, float], *, _in_atomic: bool = False
    ) -> None:
        if _in_atomic:
            self._reset_accounts_locked(alloc)
            return
        with self.atomic():
            self._reset_accounts_locked(alloc)

    def _reset_accounts_locked(self, alloc: Dict[str, float]) -> None:
        for key, _value in self._scan_prefix(kc.prefix_accounts()):
            self._raw_delete(key)
        for addr, amount in alloc.items():
            row = {
                "address": SqliteDatabase._normalize_address(addr),
                "balance": float(amount),
                "nonce": 0,
                "code": None,
                "storage": None,
            }
            self._save_account_row(row)

    def get_total_supply(self) -> float:
        return sum(float(a.get("balance", 0.0) or 0.0) for a in self.get_all_accounts())

    # ── validators ────────────────────────────────────────────────────────

    def save_validator(self, address: str, stake: float) -> None:
        with self._write_lock:
            addr = SqliteDatabase._normalize_address(address)
            row = {
                "address": addr,
                "stake": float(stake),
                "active": 1,
                "slashed": 0,
                "joined_at": int(time.time()),
            }
            self._raw_put(kc.key_validator(addr), json.dumps(row).encode("utf-8"))

    def get_validators(self, active_only: bool = True) -> List[Dict]:
        rows = self._scan_prefix(kc.prefix_validators())
        out: List[Dict] = []
        for _key, value in rows:
            row = json.loads(value.decode("utf-8"))
            if active_only and not int(row.get("active", 1)):
                continue
            out.append(row)
        return out

    def slash_validator(self, address: str) -> None:
        with self._write_lock:
            addr = SqliteDatabase._normalize_address(address)
            raw = self._raw_get(kc.key_validator(addr))
            if not raw:
                return
            row = json.loads(raw.decode("utf-8"))
            row["slashed"] = 1
            row["active"] = 0
            self._raw_put(kc.key_validator(addr), json.dumps(row).encode("utf-8"))

    # ── transactions ──────────────────────────────────────────────────────

    def _insert_transaction(self, tx: Dict) -> None:
        tx_hash = tx.get("hash", tx.get("tx_hash", "")) or ""
        if not tx_hash:
            return
        row = {
            "hash": tx_hash,
            "block_height": int(tx.get("block_height", 0) or 0),
            "from_addr": SqliteDatabase._normalize_address(tx.get("from_addr", tx.get("from", ""))),
            "to_addr": SqliteDatabase._normalize_address(tx.get("to_addr", tx.get("to", ""))),
            "value": tx.get("value", tx.get("amount", 0.0)),
            "gas": tx.get("gas", 21000),
            "gas_used": tx.get("gas_used", tx.get("gas", 21000)),
            "fee": tx.get("fee", 0.0),
            "burned": tx.get("burned", 0.0),
            "nonce": tx.get("nonce", 0),
            "tx_data": tx.get("data", tx.get("tx_data", "")),
            "status": SqliteDatabase._normalize_tx_status(tx.get("status", 1)),
            "timestamp": int(tx.get("timestamp", time.time()) or 0),
        }
        payload = json.dumps(row, ensure_ascii=False).encode("utf-8")
        self._raw_put(kc.key_tx(tx_hash), payload)
        if row["block_height"]:
            self._raw_put(kc.key_block_tx(row["block_height"], tx_hash), b"\x01")

    def _insert_tx_receipt(self, tx: Dict, block_hash: str, block_height: int) -> None:
        tx_hash = tx.get("hash", tx.get("tx_hash", "")) or ""
        if not tx_hash:
            return
        receipt = {
            "tx_hash": tx_hash,
            "block_height": int(block_height),
            "block_hash": block_hash,
            "from_addr": SqliteDatabase._normalize_address(tx.get("from_addr", tx.get("from", ""))),
            "to_addr": SqliteDatabase._normalize_address(tx.get("to_addr", tx.get("to", ""))),
            "value": tx.get("value", tx.get("amount", 0.0)),
            "fee": tx.get("fee", 0.0),
            "burned": tx.get("burned", 0.0),
            "gas_used": tx.get("gas_used", tx.get("gas", 21000)),
            "status": SqliteDatabase._normalize_tx_status(tx.get("status", 1)),
            "created_at": int(time.time()),
        }
        self._raw_put(
            kc.P_TX_RECEIPT + kc.key_tx(tx_hash)[1:],
            json.dumps(receipt).encode("utf-8"),
        )

    def save_transaction(self, tx: Dict) -> bool:
        with self._write_lock:
            try:
                self._insert_transaction(tx)
                return True
            except Exception as exc:
                print(f"[RocksDB] save_transaction error: {exc}")
                return False

    def get_transaction(self, tx_hash: str) -> Optional[Dict]:
        raw = self._raw_get(kc.key_tx(tx_hash))
        return json.loads(raw.decode("utf-8")) if raw else None

    def get_transactions_in_block(self, height: int) -> List[Dict]:
        prefix = kc.P_BLOCK_TX + kc.pack_u64(int(height))
        rows = self._scan_prefix(prefix)
        out: List[Dict] = []
        for key, _marker in rows:
            tx_hash_bytes = key[len(prefix) :]
            tx_key = kc.P_TX + tx_hash_bytes
            raw = self._raw_get(tx_key)
            if raw:
                out.append(json.loads(raw.decode("utf-8")))
        return out

    def get_recent_transactions(self, limit: int = 30) -> List[Dict]:
        rows = self._scan_prefix(kc.P_TX)
        decoded = [json.loads(v.decode("utf-8")) for _k, v in rows]
        decoded.sort(key=lambda r: (int(r.get("block_height", 0)), int(r.get("timestamp", 0))), reverse=True)
        return decoded[:limit]

    def get_tx_receipt(self, tx_hash: str) -> Optional[Dict]:
        raw = self._raw_get(kc.P_TX_RECEIPT + kc.key_tx(tx_hash)[1:])
        return json.loads(raw.decode("utf-8")) if raw else None

    def _format_receipt_row(self, row: Dict) -> Dict:
        return {
            "tx_hash": row.get("tx_hash", ""),
            "block_height": row.get("block_height", 0),
            "block_hash": row.get("block_hash", ""),
            "from": row.get("from_addr", row.get("from", "")),
            "to": row.get("to_addr", row.get("to", "")),
            "value": row.get("value", 0.0),
            "fee": row.get("fee", 0.0),
            "burned": row.get("burned", 0.0),
            "gas_used": row.get("gas_used", 0),
            "status": row.get("status", 1),
            "timestamp": row.get("created_at", row.get("timestamp", 0)),
        }

    def get_receipts_by_block(self, block_height: int) -> List[Dict]:
        height = int(block_height)
        out: List[Dict] = []
        for _key, value in self._scan_prefix(kc.P_TX_RECEIPT):
            try:
                row = json.loads(value.decode("utf-8"))
            except Exception:
                continue
            if int(row.get("block_height", 0) or 0) == height:
                out.append(self._format_receipt_row(row))
        out.sort(key=lambda r: int(r.get("timestamp", 0)))
        return out

    def _serialize_tx_row(self, row: Dict, viewer_addr: str = "") -> Dict:
        return SqliteDatabase._serialize_tx_row(row, viewer_addr)

    def _iter_transaction_rows(self) -> List[Dict]:
        rows: List[Dict] = []
        for _key, value in self._scan_prefix(kc.P_TX):
            try:
                rows.append(json.loads(value.decode("utf-8")))
            except Exception:
                continue
        return rows

    def count_transactions_by_address(
        self, address: str, direction: str = "all"
    ) -> int:
        addr = SqliteDatabase._normalize_address(address)
        count = 0
        for row in self._iter_transaction_rows():
            from_addr = SqliteDatabase._normalize_address(row.get("from_addr", ""))
            to_addr = SqliteDatabase._normalize_address(row.get("to_addr", ""))
            if direction == "sent":
                if from_addr == addr:
                    count += 1
            elif direction == "received":
                if to_addr == addr:
                    count += 1
            elif from_addr == addr or to_addr == addr:
                count += 1
        return count

    def get_transactions_by_address(
        self,
        address: str,
        limit: int = 50,
        offset: int = 0,
        direction: str = "all",
    ) -> List[Dict]:
        addr = SqliteDatabase._normalize_address(address)
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))
        matched: List[Dict] = []
        for row in self._iter_transaction_rows():
            from_addr = SqliteDatabase._normalize_address(row.get("from_addr", ""))
            to_addr = SqliteDatabase._normalize_address(row.get("to_addr", ""))
            if direction == "sent" and from_addr != addr:
                continue
            if direction == "received" and to_addr != addr:
                continue
            if direction not in ("sent", "received") and from_addr != addr and to_addr != addr:
                continue
            matched.append(row)
        matched.sort(
            key=lambda r: (int(r.get("block_height", 0)), int(r.get("timestamp", 0))),
            reverse=True,
        )
        page = matched[offset : offset + limit]
        return [self._serialize_tx_row(row, addr) for row in page]

    def get_address_activity(self, address: str) -> Dict:
        addr = SqliteDatabase._normalize_address(address)
        sent = self.count_transactions_by_address(addr, "sent")
        received = self.count_transactions_by_address(addr, "received")
        total = self.count_transactions_by_address(addr, "all")
        blocks_proposed = 0
        last_h: int | None = None
        for row in self._iter_transaction_rows():
            from_addr = SqliteDatabase._normalize_address(row.get("from_addr", ""))
            to_addr = SqliteDatabase._normalize_address(row.get("to_addr", ""))
            if from_addr == addr or to_addr == addr:
                bh = int(row.get("block_height", 0) or 0)
                if last_h is None or bh > last_h:
                    last_h = bh
        for _key, value in self._scan_prefix(kc.P_PROPOSER_AUDIT):
            try:
                audit = json.loads(value.decode("utf-8"))
            except Exception:
                continue
            if SqliteDatabase._normalize_address(audit.get("proposer", "")) == addr:
                blocks_proposed += 1
        acct = self._load_account(addr)
        return {
            "address": addr,
            "balance": float(acct.get("balance", 0.0) or 0.0),
            "nonce": int(acct.get("nonce", 0) or 0),
            "sent_count": sent,
            "received_count": received,
            "tx_count": total,
            "blocks_proposed": blocks_proposed,
            "last_tx_height": last_h,
            "is_contract": bool(acct.get("code")),
        }

    def get_proposer_audit_log(
        self,
        limit: int = 50,
        offset: int = 0,
        proposer: str = "",
    ) -> List[Dict]:
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))
        rows: List[Dict] = []
        for _key, value in self._scan_prefix(kc.P_PROPOSER_AUDIT):
            try:
                audit = json.loads(value.decode("utf-8"))
            except Exception:
                continue
            if proposer:
                want = SqliteDatabase._normalize_address(proposer)
                if SqliteDatabase._normalize_address(audit.get("proposer", "")) != want:
                    continue
            rows.append(audit)
        rows.sort(key=lambda r: int(r.get("height", 0)), reverse=True)
        page = rows[offset : offset + limit]
        return [
            {
                "height": r.get("height", 0),
                "block_hash": r.get("block_hash", ""),
                "proposer": r.get("proposer", ""),
                "tx_count": r.get("tx_count", 0),
                "total_burned": r.get("total_burned", 0.0),
                "timestamp": r.get("block_ts", r.get("timestamp", 0)),
                "recorded_at": r.get("recorded_at", 0),
            }
            for r in page
        ]

    # ── burn ──────────────────────────────────────────────────────────────

    def _insert_burn_record(self, block_height: int, burned_amount: float) -> None:
        total = self.get_total_burned() + float(burned_amount)
        row = {"block_height": int(block_height), "burned_amount": float(burned_amount), "total_burned": total}
        self._raw_put(kc.key_burn(int(block_height)), json.dumps(row).encode("utf-8"))

    def record_burn(self, block_height: int, burned_amount: float) -> None:
        with self._write_lock:
            self._insert_burn_record(block_height, burned_amount)

    def get_total_burned(self) -> float:
        rows = self._scan_prefix(kc.P_BURN)
        if not rows:
            return 0.0
        last = max(rows, key=lambda kv: kc.unpack_u64(kv[0][1:9]))
        return float(json.loads(last[1].decode("utf-8")).get("total_burned", 0.0))

    def get_burn_stats(self) -> Dict:
        total = self.get_total_burned()
        return {"total_burned": total, "burn_address": ""}

    # ── block commit ──────────────────────────────────────────────────────

    def persist_block_atomic(
        self,
        block: Dict,
        transactions: List[Dict],
        burned_amount: float = 0.0,
        burn_address: str = "",
    ) -> bool:
        with self.atomic():
            try:
                self._persist_block_locked(block, transactions, burned_amount, burn_address)
                return True
            except Exception as exc:
                print(f"[RocksDB] persist_block_atomic error: {exc}")
                return False

    def _persist_block_locked(
        self,
        block: Dict,
        transactions: List[Dict],
        burned_amount: float = 0.0,
        burn_address: str = "",
    ) -> None:
        self._insert_block(block)
        block_hash = block.get("hash", block.get("block_hash", ""))
        block_height = int(block.get("height", block.get("number", 0)) or 0)
        for tx in transactions:
            self._insert_transaction(tx)
            self._insert_tx_receipt(tx, block_hash, block_height)
        if burned_amount > 0:
            self._insert_burn_record(block_height, burned_amount)
            if burn_address:
                self._apply_balance_delta(burn_address, burned_amount)

    # ── truncate / reorg ────────────────────────────────────────────────

    def reorg_truncate_above(self, height: int) -> None:
        cut = int(height)
        for key, _value in self._scan_prefix(kc.prefix_block_heights()):
            if kc.unpack_u64(key[1:9]) > cut:
                self._raw_delete(key)
        for key, _value in list(self._scan_prefix(kc.P_BLOCK_TX)):
            if len(key) >= 9 and kc.unpack_u64(key[1:9]) > cut:
                self._raw_delete(key)
        for key, value in list(self._scan_prefix(kc.P_TX)):
            try:
                row = json.loads(value.decode("utf-8"))
            except Exception:
                continue
            if int(row.get("block_height", 0) or 0) > cut:
                self._raw_delete(key)
        for key, value in list(self._scan_prefix(kc.P_TX_RECEIPT)):
            try:
                row = json.loads(value.decode("utf-8"))
            except Exception:
                continue
            if int(row.get("block_height", 0) or 0) > cut:
                self._raw_delete(key)
        for key, _value in self._scan_prefix(kc.P_PROPOSER_AUDIT):
            if kc.unpack_u64(key[1:9]) > cut:
                self._raw_delete(key)
        for key, _value in self._scan_prefix(kc.P_BURN):
            if kc.unpack_u64(key[1:9]) > cut:
                self._raw_delete(key)
        for key, value in list(self._scan_prefix(kc.P_STATE_ROOT_MM)):
            if len(key) >= 9 and kc.unpack_u64(key[1:9]) > cut:
                self._raw_delete(key)

    def truncate_chain_state(self, height: int) -> int:
        with self.atomic():
            before = self.get_chain_tip()
            self.reorg_truncate_above(int(height))
            return max(0, before - int(height))

    def truncate_blocks_above(self, height: int) -> int:
        return self.truncate_chain_state(height)

    def truncate_all_blocks(self) -> int:
        count = 0
        with self.atomic():
            for key, _value in list(self._scan_prefix(kc.prefix_block_heights())):
                self._raw_delete(key)
                count += 1
        return count

    # ── observability stubs (index tables optional in P1) ───────────────

    def record_state_root_mismatch(
        self,
        height: int,
        expected_root: str,
        computed_root: str,
        source: str = "p2p",
        proposer: str = "",
        *,
        _no_commit: bool = False,
    ) -> None:
        row = {
            "height": int(height),
            "expected_root": expected_root,
            "computed_root": computed_root,
            "source": source,
            "proposer": proposer,
            "created_at": int(time.time()),
        }
        key = kc.P_STATE_ROOT_MM + kc.pack_u64(int(height)) + computed_root[:8].encode()
        self._raw_put(key, json.dumps(row).encode("utf-8"))

    def record_tx_propagation_event(
        self,
        tx_hash: str,
        stage: str,
        *,
        node_id: str = "",
        peer_id: str = "",
        block_height: int = 0,
        detail: Dict | None = None,
        _no_commit: bool = False,
    ) -> None:
        row = {
            "tx_hash": tx_hash,
            "stage": stage,
            "node_id": node_id,
            "peer_id": peer_id,
            "block_height": int(block_height),
            "detail": detail or {},
            "created_at": int(time.time()),
        }
        key = kc.P_TX_PROP + kc.key_tx(tx_hash)[1:] + stage.encode("utf-8")[:16]
        self._raw_put(key, json.dumps(row).encode("utf-8"))

    def get_stats(self) -> Dict:
        return {
            "height": self.get_chain_tip(),
            "total_transactions": len(self._scan_prefix(kc.P_TX)),
            "total_accounts": len(self._scan_prefix(kc.prefix_accounts())),
            "total_burned": self.get_total_burned(),
            "total_supply": self.get_total_supply(),
            "engine": self.engine,
        }

    def save_slash_event(self, validator: str, reason: str, epoch: int, penalty: int) -> None:
        events = self.get_meta("slash_events", []) or []
        events.append(
            {
                "validator": validator,
                "reason": reason,
                "epoch": int(epoch),
                "penalty": int(penalty),
                "timestamp": int(time.time()),
            }
        )
        self.set_meta("slash_events", events[-500:])

    def get_slash_events(self, limit: int = 100) -> List[Dict]:
        events = self.get_meta("slash_events", []) or []
        return list(events)[-int(limit) :]

    def get_chain_metrics(self, window: int = 32) -> Dict:
        tip = self.get_chain_tip()
        tx_rows = self._iter_transaction_rows()
        receipt_rows = self._scan_prefix(kc.P_TX_RECEIPT)
        audit_rows = self._scan_prefix(kc.P_PROPOSER_AUDIT)
        blocks = self.get_latest_blocks(limit=max(2, int(window)))
        avg_block_time = 0.0
        if len(blocks) >= 2:
            ordered = sorted(blocks, key=lambda b: int(b.get("height", b.get("number", 0)) or 0))
            intervals = []
            for i in range(1, len(ordered)):
                dt = int(ordered[i].get("timestamp", 0)) - int(ordered[i - 1].get("timestamp", 0))
                if dt > 0:
                    intervals.append(dt)
            if intervals:
                avg_block_time = sum(intervals) / len(intervals)
        return {
            "height": tip,
            "tx_count": len(tx_rows),
            "receipt_count": len(receipt_rows),
            "proposer_audit_count": len(audit_rows),
            "receipts_enabled": True,
            "proposer_audit_enabled": True,
            "state_root_strict_p2p": True,
            "avg_block_time_sec": round(avg_block_time, 2),
            "target_block_time_sec": 15.0,
            "blocks_sampled": len(blocks),
            "burn_last_window": round(
                sum(float(b.get("total_burned", 0) or 0) for b in blocks), 6
            ),
            "engine": self.engine,
        }
