#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RocksDB chain store — hot path (blocks, state, meta) via abs_native RocksEngine.

Reads are lock-free (RocksDB MVCC). Writes are serialized through WriteBatch commits.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from storage import keycodec as kc
from storage.database import Database as SqliteDatabase

logger = logging.getLogger(__name__)


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
        block_cache_mb: int = 0,
        write_buffer_mb: int = 0,
        column_families: bool = False,
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
        self.block_cache_mb = int(block_cache_mb or 0)
        self.write_buffer_mb = int(write_buffer_mb or 0)
        self.column_families = bool(column_families)
        self._write_lock = threading.RLock()
        self._pending_batch: Any | None = None
        os.makedirs(db_path, exist_ok=True)
        engine_kwargs = {
            "create_if_missing": True,
            "sync_writes": sync in ("FULL", "EXTRA", "STRICT"),
            "block_cache_mb": self.block_cache_mb,
            "write_buffer_mb": self.write_buffer_mb,
        }
        # Older wheels may lack column_families kwarg — only pass when supported.
        try:
            import inspect

            sig = inspect.signature(abs_native.RocksEngine)
            if "column_families" in sig.parameters:
                engine_kwargs["column_families"] = self.column_families
            elif self.column_families:
                raise RuntimeError(
                    "rocksdb_column_families requires a newer abs_native wheel"
                )
        except (TypeError, ValueError):
            if self.column_families:
                engine_kwargs["column_families"] = self.column_families
        self._engine = abs_native.RocksEngine(db_path, **engine_kwargs)
        self._schema_version = (
            "rocksdb-chain-v2-cf" if self.column_families else "rocksdb-chain-v1"
        )
        self._root_acc: Any | None = None
        self._batch_acc_dirty: dict[str, bytes | None] = {}
        self._json_decode_failures: int = 0
        self._ensure_schema()

    def _loads_json_or_none(self, raw: bytes | None, *, context: str) -> Optional[Dict]:
        """Decode a Rocks JSON blob; corrupt rows bump the fail-closed counter."""
        if raw is None:
            return None
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            self._json_decode_failures += 1
            logger.warning(
                "[RocksStore] corrupt %s (decode_failures=%s): %s",
                context,
                self._json_decode_failures,
                exc,
            )
            return None
        return data if isinstance(data, dict) else None

    def _ensure_schema(self) -> None:
        existing = self._raw_get(kc.key_meta("schema_version"))
        target = self._schema_version.encode("utf-8")
        if existing is None:
            self._raw_put(kc.key_meta("schema_version"), target)
            return
        # One-way honesty: bump meta when CF mode is enabled on a legacy DB.
        if self.column_families and existing != target:
            self._raw_put(kc.key_meta("schema_version"), target)

    def initialize(self) -> None:
        self._ensure_schema()
        if not self.get_meta("tx_addr_index_v1"):
            with self._write_lock:
                for row in self._iter_transaction_rows():
                    self._insert_tx_indexes(row)
                self.set_meta("tx_addr_index_v1", True)
        if not self.get_meta("tx_recent_index_v1"):
            with self._write_lock:
                for row in self._iter_transaction_rows():
                    tx_hash = row.get("hash", row.get("tx_hash", "")) or ""
                    if not tx_hash:
                        continue
                    bh = int(row.get("block_height", 0) or 0)
                    ts = int(row.get("timestamp", 0) or 0)
                    self._raw_put(kc.key_tx_recent_index(bh, ts, tx_hash), b"\x01")
                self.set_meta("tx_recent_index_v1", True)

    # ── low-level I/O ─────────────────────────────────────────────────────

    def _raw_get(self, key: bytes) -> Optional[bytes]:
        val = self._engine.get(key)
        return bytes(val) if val is not None else None

    def _drop_root_acc(self) -> None:
        self._root_acc = None

    def _root_acc_enabled(self) -> bool:
        try:
            import abs_native  # type: ignore

            return hasattr(abs_native, "StateRootAccumulator")
        except Exception:
            return False

    def _ensure_root_acc(self) -> Any | None:
        if self._root_acc is not None:
            return self._root_acc
        if not self._root_acc_enabled():
            return None
        import abs_native  # type: ignore

        acc = abs_native.StateRootAccumulator()
        blobs = [value for _key, value in self._scan_prefix(kc.prefix_accounts())]
        if blobs:
            acc.load_from_blobs(blobs)
        self._root_acc = acc
        return acc

    def _account_key_address(self, key: bytes) -> str:
        return key[len(kc.P_ACCOUNT) :].decode("utf-8")

    def _root_acc_upsert_blob(self, value: bytes) -> None:
        acc = self._ensure_root_acc()
        if acc is not None:
            acc.upsert_account_blob(value)

    def _root_acc_remove(self, address: str) -> None:
        if self._root_acc is not None:
            self._root_acc.remove_account(address)

    def _flush_batch_acc_dirty(self) -> None:
        if not self._batch_acc_dirty:
            return
        acc = self._ensure_root_acc()
        if acc is not None:
            for addr, value in self._batch_acc_dirty.items():
                if value is None:
                    acc.remove_account(addr)
                else:
                    acc.upsert_account_blob(value)
        self._batch_acc_dirty.clear()

    def _raw_put(self, key: bytes, value: bytes) -> None:
        if key.startswith(kc.P_ACCOUNT):
            if self._pending_batch is not None:
                self._batch_acc_dirty[self._account_key_address(key)] = value
            else:
                self._root_acc_upsert_blob(value)
        if self._pending_batch is not None:
            self._pending_batch.put(key, value)
            return
        self._engine.put(key, value)

    def _raw_delete(self, key: bytes) -> None:
        if key.startswith(kc.P_ACCOUNT):
            if self._pending_batch is not None:
                self._batch_acc_dirty[self._account_key_address(key)] = None
            else:
                self._root_acc_remove(self._account_key_address(key))
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
                self._flush_batch_acc_dirty()
            except Exception:
                raise
            finally:
                self._pending_batch = None
                self._batch_acc_dirty.clear()

    def close(self) -> None:
        self._engine = None  # type: ignore[assignment]

    def backup_to(self, dest_path: str) -> bool:
        try:
            if os.path.isdir(dest_path):
                shutil.rmtree(dest_path)
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
        except Exception as exc:
            text = raw.decode("utf-8", errors="replace")
            stripped = text.strip()
            # Corrupt JSON object/array/string → fail-closed default.
            # Legacy plain-string meta (e.g. schema_version) is not JSON.
            if stripped[:1] in "{\"[":
                self._json_decode_failures += 1
                logger.warning(
                    "[RocksStore] corrupt meta %s (decode_failures=%s): %s",
                    key,
                    self._json_decode_failures,
                    exc,
                )
                # Fail-closed: never return a garbage string as valid meta.
                return default
            return text if text else default

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
        self._touch_live_state_root_meta(block)

    def _touch_live_state_root_meta(self, block: Dict) -> None:
        state_root = str(block.get("state_root", "") or "").strip()
        if not state_root:
            return
        height = int(block.get("height", block.get("number", 0)) or 0)
        self._raw_put(kc.key_meta("state_root"), state_root.encode("utf-8"))
        self._raw_put(kc.key_meta("live_state_root"), state_root.encode("utf-8"))
        self._raw_put(
            kc.key_meta("live_state_root_height"),
            str(height).encode("utf-8"),
        )

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
        return self._loads_json_or_none(raw, context=f"block height={height}")

    def get_block_by_hash(self, block_hash: str) -> Optional[Dict]:
        raw_h = self._raw_get(kc.key_block_hash_to_height(block_hash))
        if not raw_h:
            return None
        return self.get_block(kc.unpack_u64(raw_h))

    def get_latest_blocks(self, limit: int = 20) -> List[Dict]:
        rows = self._scan_prefix(kc.prefix_block_heights())
        blocks: List[Dict] = []
        for _key, value in sorted(rows, key=lambda kv: kc.unpack_u64(kv[0][1:9]), reverse=True)[:limit]:
            try:
                blocks.append(json.loads(value.decode("utf-8")))
            except Exception as exc:
                self._json_decode_failures += 1
                logger.warning(
                    "[RocksStore] corrupt latest_block row skipped "
                    "(decode_failures=%s): %s",
                    self._json_decode_failures,
                    exc,
                )
                continue
        return blocks

    def get_chain_tip(self) -> int:
        rows = self._scan_prefix(kc.prefix_block_heights())
        if not rows:
            return 0
        return max(kc.unpack_u64(key[1:9]) for key, _ in rows)

    def get_last_block(self) -> Optional[Dict]:
        rows = self._scan_prefix(kc.prefix_block_heights())
        if not rows:
            return None
        tip = max(kc.unpack_u64(key[1:9]) for key, _ in rows)
        return self.get_block(tip)

    # ── accounts / state ──────────────────────────────────────────────────

    def _load_account(self, address: str) -> Dict[str, Any]:
        from runtime.amount import account_satoshi, dual_write_balance

        raw = self._raw_get(kc.key_account(address))
        if not raw:
            return {
                "address": SqliteDatabase._normalize_address(address),
                "balance": 0.0,
                "balance_satoshi": 0,
                "nonce": 0,
                "code": None,
                "storage": None,
            }
        row = self._loads_json_or_none(raw, context=f"account {address}")
        if row is None:
            return {
                "address": SqliteDatabase._normalize_address(address),
                "balance": 0.0,
                "balance_satoshi": 0,
                "nonce": 0,
                "code": None,
                "storage": None,
            }
        # Backfill satoshi for legacy float-only rows (in-memory; persisted on next write)
        if row.get("balance_satoshi") is None:
            dual_write_balance(row, row.get("balance", 0) or 0)
        else:
            row["balance_satoshi"] = account_satoshi(row)
            row["balance"] = float(row.get("balance", 0) or 0)
        return row

    def _save_account_row(self, row: Dict[str, Any]) -> None:
        from runtime.amount import dual_write_balance, from_satoshi_float

        addr = SqliteDatabase._normalize_address(row.get("address", ""))
        row["address"] = addr
        if row.get("balance_satoshi") is not None:
            sat = max(0, int(row["balance_satoshi"]))
            row["balance_satoshi"] = sat
            row["balance"] = from_satoshi_float(sat)
        else:
            dual_write_balance(row, row.get("balance", 0) or 0)
        self._raw_put(kc.key_account(addr), json.dumps(row, ensure_ascii=False).encode("utf-8"))

    def get_balance(self, address: str) -> float:
        from runtime.amount import account_balance_abs

        return account_balance_abs(self._load_account(address))

    def get_balance_satoshi(self, address: str) -> int:
        from runtime.amount import account_satoshi

        return account_satoshi(self._load_account(address))

    def get_nonce(self, address: str) -> int:
        return int(self._load_account(address).get("nonce", 0) or 0)

    def get_account(self, address: str) -> Optional[Dict]:
        from runtime.amount import account_satoshi

        row = self._load_account(address)
        sat = account_satoshi(row)
        if sat == 0 and row["nonce"] == 0 and not row.get("code") and not row.get("storage"):
            raw = self._raw_get(kc.key_account(address))
            return None if raw is None else row
        return row

    def _apply_balance_delta(self, address: str, delta: float) -> None:
        from runtime.amount import apply_delta_satoshi, dual_write_balance, from_satoshi_float

        row = self._load_account(address)
        cur_sat = int(row.get("balance_satoshi", 0) or 0)
        new_sat = apply_delta_satoshi(cur_sat, delta)
        dual_write_balance(row, from_satoshi_float(new_sat))
        # dual_write from float of new_sat is exact for representable amounts
        row["balance_satoshi"] = new_sat
        row["balance"] = from_satoshi_float(new_sat)
        self._save_account_row(row)

    def balance_delta(self, address: str, delta: float) -> None:
        self._apply_balance_delta(address, delta)

    def update_balance(self, address: str, delta: float) -> float:
        with self._write_lock:
            self._apply_balance_delta(address, delta)
            return self.get_balance(address)

    def set_balance(self, address: str, balance: float) -> None:
        from runtime.amount import dual_write_balance

        with self._write_lock:
            row = self._load_account(address)
            dual_write_balance(row, balance)
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
        from runtime.amount import dual_write_balance

        with self._write_lock:
            row = self._load_account(address)
            dual_write_balance(row, balance)
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
            try:
                out.append(json.loads(value.decode("utf-8")))
            except Exception as exc:
                self._json_decode_failures += 1
                logger.warning(
                    "[RocksStore] corrupt account row skipped "
                    "(decode_failures=%s): %s",
                    self._json_decode_failures,
                    exc,
                )
                continue
        return sorted(out, key=lambda r: str(r.get("address", "")))

    def get_live_state_root_meta(self) -> tuple[str, int]:
        """Cached root from last committed block header (observability fast path)."""
        raw_root = self._raw_get(kc.key_meta("live_state_root"))
        raw_h = self._raw_get(kc.key_meta("live_state_root_height"))
        root = raw_root.decode("utf-8") if raw_root else ""
        try:
            height = int(raw_h.decode("utf-8")) if raw_h else -1
        except Exception:
            height = -1
        return root, height

    def compute_state_root(self) -> str:
        """Canonical state root via native accumulator or account blob scan."""
        from execution.state_root import compute_state_root_from_blobs

        if self._batch_acc_dirty or self._pending_batch is not None:
            by_addr: dict[str, bytes] = {}
            for key, value in self._scan_prefix(kc.prefix_accounts()):
                by_addr[self._account_key_address(key)] = value
            for addr, value in self._batch_acc_dirty.items():
                if value is None:
                    by_addr.pop(addr, None)
                else:
                    by_addr[addr] = value
            return compute_state_root_from_blobs(list(by_addr.values()))

        acc = self._ensure_root_acc()
        if acc is not None:
            return acc.root()
        if hasattr(self._engine, "state_root_from_account_prefix"):
            return self._engine.state_root_from_account_prefix(
                kc.prefix_accounts(),
                100_000,
            )
        blobs = [value for _key, value in self._scan_prefix(kc.prefix_accounts())]
        return compute_state_root_from_blobs(blobs)

    def reset_accounts_from_alloc(
        self, alloc: Dict[str, float], *, _in_atomic: bool = False
    ) -> None:
        if _in_atomic:
            self._reset_accounts_locked(alloc)
            return
        with self.atomic():
            self._reset_accounts_locked(alloc)

    def _reset_accounts_locked(self, alloc: Dict[str, float]) -> None:
        self._drop_root_acc()
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
        from runtime.amount import account_balance_abs

        return sum(account_balance_abs(a) for a in self.get_all_accounts())

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
            try:
                row = json.loads(value.decode("utf-8"))
            except Exception as exc:
                self._json_decode_failures += 1
                logger.warning(
                    "[RocksStore] corrupt validator row skipped "
                    "(decode_failures=%s): %s",
                    self._json_decode_failures,
                    exc,
                )
                continue
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
            row = self._loads_json_or_none(raw, context=f"slash_validator {addr}")
            if row is None:
                return
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
            # Omit / None / unknown → fail-closed 0 (never invent success).
            "status": SqliteDatabase._normalize_tx_status(tx.get("status")),
            "timestamp": int(tx.get("timestamp", time.time()) or 0),
        }
        payload = json.dumps(row, ensure_ascii=False).encode("utf-8")
        self._raw_put(kc.key_tx(tx_hash), payload)
        if row["block_height"]:
            self._raw_put(kc.key_block_tx(row["block_height"], tx_hash), b"\x01")
        self._insert_tx_indexes(row)

    def _insert_tx_indexes(self, row: Dict) -> None:
        tx_hash = row.get("hash", row.get("tx_hash", "")) or ""
        if not tx_hash:
            return
        bh = int(row.get("block_height", 0) or 0)
        from_addr = row.get("from_addr", "")
        to_addr = row.get("to_addr", "")
        if from_addr:
            self._raw_put(kc.key_tx_from_index(from_addr, bh, tx_hash), b"\x01")
        if to_addr:
            self._raw_put(kc.key_tx_to_index(to_addr, bh, tx_hash), b"\x01")
        ts = int(row.get("timestamp", 0) or 0)
        self._raw_put(kc.key_tx_recent_index(bh, ts, tx_hash), b"\x01")

    def _delete_tx_indexes(self, row: Dict) -> None:
        tx_hash = row.get("hash", row.get("tx_hash", "")) or ""
        if not tx_hash:
            return
        bh = int(row.get("block_height", 0) or 0)
        from_addr = row.get("from_addr", "")
        to_addr = row.get("to_addr", "")
        if from_addr:
            self._raw_delete(kc.key_tx_from_index(from_addr, bh, tx_hash))
        if to_addr:
            self._raw_delete(kc.key_tx_to_index(to_addr, bh, tx_hash))
        ts = int(row.get("timestamp", 0) or 0)
        self._raw_delete(kc.key_tx_recent_index(bh, ts, tx_hash))

    def _tx_hash_from_index_key(self, key: bytes, prefix: bytes) -> str:
        body = key[len(prefix) :]
        if len(body) < 8 + 32:
            return ""
        return "0x" + body[8:].hex()

    def _tx_hash_from_recent_key(self, key: bytes) -> str:
        body = key[len(kc.P_TX_RECENT) :]
        if len(body) < 16 + 32:
            return ""
        return "0x" + body[16:].hex()

    def _rows_from_address_index(
        self, addr: str, direction: str
    ) -> List[Dict]:
        addr = SqliteDatabase._normalize_address(addr)
        prefixes: List[bytes] = []
        if direction in ("all", "sent"):
            prefixes.append(kc.prefix_tx_from(addr))
        if direction in ("all", "received"):
            prefixes.append(kc.prefix_tx_to(addr))
        seen: set[str] = set()
        rows: List[Dict] = []
        for prefix in prefixes:
            for key, _marker in self._scan_prefix(prefix):
                tx_hash = self._tx_hash_from_index_key(key, prefix)
                if not tx_hash or tx_hash in seen:
                    continue
                seen.add(tx_hash)
                raw = self._raw_get(kc.key_tx(tx_hash))
                if raw:
                    try:
                        rows.append(json.loads(raw.decode("utf-8")))
                    except Exception as exc:
                        self._json_decode_failures += 1
                        logger.warning(
                            "[RocksStore] corrupt address_tx row skipped "
                            "(decode_failures=%s): %s",
                            self._json_decode_failures,
                            exc,
                        )
                        continue
        rows.sort(
            key=lambda r: (int(r.get("block_height", 0)), int(r.get("timestamp", 0))),
            reverse=True,
        )
        return rows

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
            # Omit / None / unknown → fail-closed 0 (never invent success).
            "status": SqliteDatabase._normalize_tx_status(tx.get("status")),
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
        return self._loads_json_or_none(raw, context=f"tx {tx_hash[:16]}")

    def get_transactions_in_block(self, height: int) -> List[Dict]:
        prefix = kc.P_BLOCK_TX + kc.pack_u64(int(height))
        rows = self._scan_prefix(prefix)
        out: List[Dict] = []
        for key, _marker in rows:
            tx_hash_bytes = key[len(prefix) :]
            tx_key = kc.P_TX + tx_hash_bytes
            raw = self._raw_get(tx_key)
            if raw:
                try:
                    out.append(json.loads(raw.decode("utf-8")))
                except Exception as exc:
                    self._json_decode_failures += 1
                    logger.warning(
                        "[RocksStore] corrupt block_tx row skipped "
                        "(decode_failures=%s): %s",
                        self._json_decode_failures,
                        exc,
                    )
                    continue
        return out

    def get_recent_transactions(self, limit: int = 30) -> List[Dict]:
        limit = max(1, min(int(limit), 200))
        out: List[Dict] = []
        for key, _marker in self._scan_prefix(kc.prefix_tx_recent(), limit=limit * 2):
            tx_hash = self._tx_hash_from_recent_key(key)
            if not tx_hash:
                continue
            raw = self._raw_get(kc.key_tx(tx_hash))
            if raw:
                try:
                    out.append(json.loads(raw.decode("utf-8")))
                except Exception as exc:
                    self._json_decode_failures += 1
                    logger.warning(
                        "[RocksStore] corrupt recent_tx row skipped "
                        "(decode_failures=%s): %s",
                        self._json_decode_failures,
                        exc,
                    )
                    continue
            if len(out) >= limit:
                break
        return out

    def get_tx_receipt(self, tx_hash: str) -> Optional[Dict]:
        raw = self._raw_get(kc.P_TX_RECEIPT + kc.key_tx(tx_hash)[1:])
        return self._loads_json_or_none(raw, context=f"receipt {tx_hash[:16]}")

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
            "status": SqliteDatabase._normalize_tx_status(row.get("status")),
            "timestamp": row.get("created_at", row.get("timestamp", 0)),
        }

    def get_receipts_by_block(self, block_height: int) -> List[Dict]:
        height = int(block_height)
        out: List[Dict] = []
        for tx in self.get_transactions_in_block(height):
            tx_hash = tx.get("hash", tx.get("tx_hash", "")) or ""
            rcpt = self.get_tx_receipt(tx_hash) if tx_hash else None
            if rcpt:
                out.append(self._format_receipt_row(rcpt))
            else:
                out.append(
                    self._format_receipt_row(
                        {
                            **tx,
                            "tx_hash": tx_hash,
                            "block_hash": "",
                            "created_at": tx.get("timestamp", 0),
                        }
                    )
                )
        out.sort(key=lambda r: int(r.get("timestamp", 0)))
        return out

    def _serialize_tx_row(self, row: Dict, viewer_addr: str = "") -> Dict:
        viewer = SqliteDatabase._normalize_address(viewer_addr)
        from_addr = SqliteDatabase._normalize_address(row.get("from_addr", ""))
        to_addr = SqliteDatabase._normalize_address(row.get("to_addr", ""))
        direction = "unknown"
        if viewer:
            if from_addr == viewer and to_addr == viewer:
                direction = "self"
            elif from_addr == viewer:
                direction = "sent"
            elif to_addr == viewer:
                direction = "received"
        return {
            "hash": row.get("hash", ""),
            "block_height": row.get("block_height", 0),
            "from": from_addr,
            "to": to_addr,
            "value": float(row.get("value", 0.0)),
            "fee": float(row.get("fee", 0.0)),
            "burned": float(row.get("burned", 0.0)),
            "gas_used": int(row.get("gas_used", row.get("gas", 21000))),
            "status": SqliteDatabase._normalize_tx_status(row.get("status")),
            "timestamp": int(row.get("timestamp", 0)),
            "direction": direction,
        }

    def _iter_transaction_rows(self) -> List[Dict]:
        rows: List[Dict] = []
        for _key, value in self._scan_prefix(kc.P_TX):
            try:
                rows.append(json.loads(value.decode("utf-8")))
            except Exception as exc:
                self._json_decode_failures += 1
                logger.warning(
                    "[RocksStore] corrupt TX row skipped (decode_failures=%s): %s",
                    self._json_decode_failures,
                    exc,
                )
                continue
        return rows

    def count_transactions_by_address(
        self, address: str, direction: str = "all"
    ) -> int:
        addr = SqliteDatabase._normalize_address(address)
        if direction == "sent":
            return len(self._scan_prefix(kc.prefix_tx_from(addr)))
        if direction == "received":
            return len(self._scan_prefix(kc.prefix_tx_to(addr)))
        hashes: set[str] = set()
        for prefix in (kc.prefix_tx_from(addr), kc.prefix_tx_to(addr)):
            for key, _marker in self._scan_prefix(prefix):
                tx_hash = self._tx_hash_from_index_key(key, prefix)
                if tx_hash:
                    hashes.add(tx_hash)
        return len(hashes)

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
        matched = self._rows_from_address_index(addr, direction)
        page = matched[offset : offset + limit]
        return [self._serialize_tx_row(row, addr) for row in page]

    def get_address_activity(self, address: str) -> Dict:
        addr = SqliteDatabase._normalize_address(address)
        sent = self.count_transactions_by_address(addr, "sent")
        received = self.count_transactions_by_address(addr, "received")
        total = self.count_transactions_by_address(addr, "all")
        blocks_proposed = 0
        last_h: int | None = None
        for row in self._rows_from_address_index(addr, "all"):
            bh = int(row.get("block_height", 0) or 0)
            if last_h is None or bh > last_h:
                last_h = bh
        for _key, value in self._scan_prefix(kc.P_PROPOSER_AUDIT):
            try:
                audit = json.loads(value.decode("utf-8"))
            except Exception as exc:
                self._json_decode_failures += 1
                logger.warning(
                    "[RocksStore] corrupt proposer_audit row skipped "
                    "(decode_failures=%s): %s",
                    self._json_decode_failures,
                    exc,
                )
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
            except Exception as exc:
                self._json_decode_failures += 1
                logger.warning(
                    "[RocksStore] corrupt proposer_audit list row skipped "
                    "(decode_failures=%s): %s",
                    self._json_decode_failures,
                    exc,
                )
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

    # ── bridge (cross-chain) ─────────────────────────────────────────────

    @staticmethod
    def bridge_credit_key(from_chain: str, event_tx_hash: str, log_index: int = 0) -> str:
        """Replay key from source event identity (not claim recipient/amount)."""
        from crypto import native

        raw = (
            f"{(from_chain or '').strip()}:"
            f"{(event_tx_hash or '').strip()}:"
            f"{int(log_index)}"
        ).lower()
        return native.sha256_hex(raw.encode())

    def save_bridge_lock(
        self,
        from_addr: str,
        to_chain: str,
        to_addr: str,
        amount: float,
        tx_hash: str,
    ) -> None:
        row = {
            "tx_hash": tx_hash,
            "from_addr": from_addr,
            "to_chain": to_chain,
            "to_addr": to_addr,
            "amount": float(amount),
            "status": "pending",
            "created_at": int(time.time()),
        }
        with self._write_lock:
            self._raw_put(kc.key_bridge_lock(tx_hash), json.dumps(row).encode("utf-8"))

    def confirm_bridge_lock(self, tx_hash: str) -> None:
        with self._write_lock:
            raw = self._raw_get(kc.key_bridge_lock(tx_hash))
            if not raw:
                return
            row = self._loads_json_or_none(raw, context=f"bridge_lock {tx_hash[:16]}")
            if row is None:
                return
            row["status"] = "confirmed"
            self._raw_put(kc.key_bridge_lock(tx_hash), json.dumps(row).encode("utf-8"))

    def get_bridge_locks(self, limit: int = 50) -> List[Dict]:
        limit = max(1, min(int(limit), 5000))
        rows: List[Dict] = []
        for _key, value in self._scan_prefix(kc.prefix_bridge_locks()):
            try:
                rows.append(json.loads(value.decode("utf-8")))
            except Exception as exc:
                self._json_decode_failures += 1
                logger.warning(
                    "[RocksStore] corrupt bridge_lock row skipped "
                    "(decode_failures=%s): %s",
                    self._json_decode_failures,
                    exc,
                )
                continue
        rows.sort(key=lambda r: int(r.get("created_at", 0) or 0), reverse=True)
        return rows[:limit]

    def has_bridge_credit(self, credit_key: str) -> bool:
        return self._raw_get(kc.key_bridge_credit(credit_key)) is not None

    def save_bridge_credit(
        self,
        event_tx_hash: str,
        recipient: str,
        amount: float,
        from_chain: str,
        log_index: int = 0,
    ) -> str:
        key = self.bridge_credit_key(from_chain, event_tx_hash, log_index)
        if self.has_bridge_credit(key):
            return key
        row = {
            "credit_key": key,
            "l1_tx_hash": event_tx_hash,
            "recipient": recipient,
            "amount": float(amount),
            "from_chain": from_chain,
            "log_index": int(log_index),
            "credited_at": int(time.time()),
        }
        with self._write_lock:
            self._raw_put(kc.key_bridge_credit(key), json.dumps(row).encode("utf-8"))
        return key

    def claim_and_credit_bridge_event(
        self,
        from_chain: str,
        event_tx_hash: str,
        recipient: str,
        amount: float,
        log_index: int = 0,
        abs_tx_hash: str = "",
    ) -> Dict:
        """Insert-if-absent replay claim then credit recipient in one Rocks batch."""
        key = self.bridge_credit_key(from_chain, event_tx_hash, log_index)
        with self.atomic():
            if self.has_bridge_credit(key):
                return {"credited": False, "duplicate": True, "credit_key": key}
            row = {
                "credit_key": key,
                "l1_tx_hash": event_tx_hash,
                "recipient": recipient,
                "amount": float(amount),
                "from_chain": from_chain,
                "log_index": int(log_index),
                "credited_at": int(time.time()),
            }
            self._raw_put(kc.key_bridge_credit(key), json.dumps(row).encode("utf-8"))
            self.balance_delta(recipient, float(amount))
            lock_hash = (abs_tx_hash or event_tx_hash or "").strip()
            if lock_hash:
                raw = self._raw_get(kc.key_bridge_lock(lock_hash))
                if raw:
                    lock_row = self._loads_json_or_none(
                        raw, context=f"bridge_lock {lock_hash[:16]}"
                    )
                    if lock_row is not None:
                        lock_row["status"] = "confirmed"
                        self._raw_put(
                            kc.key_bridge_lock(lock_hash),
                            json.dumps(lock_row).encode("utf-8"),
                        )
        return {"credited": True, "duplicate": False, "credit_key": key}

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
        row = self._loads_json_or_none(last[1], context="burn_total")
        if row is None:
            return 0.0
        return float(row.get("total_burned", 0.0) or 0.0)

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
        self._drop_root_acc()
        cut = int(height)
        for key, value in list(self._scan_prefix(kc.prefix_block_heights())):
            h = kc.unpack_u64(key[1:9])
            if h <= cut:
                continue
            try:
                block = json.loads(value.decode("utf-8"))
                block_hash = block.get("hash", block.get("block_hash", "")) or ""
                if block_hash:
                    self._raw_delete(kc.key_block_hash_to_height(block_hash))
            except Exception as exc:
                self._json_decode_failures += 1
                logger.warning(
                    "reorg_truncate_above: corrupt block JSON at height>%s "
                    "(decode_failures=%s): %s",
                    cut,
                    self._json_decode_failures,
                    exc,
                )
            self._raw_delete(key)
        for key, _value in list(self._scan_prefix(kc.P_BLOCK_TX)):
            if len(key) >= 9 and kc.unpack_u64(key[1:9]) > cut:
                self._raw_delete(key)
        for key, value in list(self._scan_prefix(kc.P_TX)):
            try:
                row = json.loads(value.decode("utf-8"))
            except Exception as exc:
                self._json_decode_failures += 1
                logger.warning(
                    "reorg_truncate_above: corrupt tx JSON above height>%s "
                    "(decode_failures=%s): %s",
                    cut,
                    self._json_decode_failures,
                    exc,
                )
                self._raw_delete(key)
                continue
            if int(row.get("block_height", 0) or 0) > cut:
                self._delete_tx_indexes(row)
                self._raw_delete(key)
        for key, value in list(self._scan_prefix(kc.P_TX_RECEIPT)):
            try:
                row = json.loads(value.decode("utf-8"))
            except Exception as exc:
                self._json_decode_failures += 1
                logger.warning(
                    "reorg_truncate_above: corrupt receipt JSON above height>%s "
                    "(decode_failures=%s): %s",
                    cut,
                    self._json_decode_failures,
                    exc,
                )
                self._raw_delete(key)
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
        self._purge_height_scoped_indexes(cut)
        tip = self.get_block(cut)
        if tip:
            self._touch_live_state_root_meta(tip)
        else:
            for meta_key in ("live_state_root", "live_state_root_height", "state_root"):
                self._raw_delete(kc.key_meta(meta_key))

    def _purge_height_scoped_indexes(self, cut: int) -> None:
        """Remove secondary Rocks indexes tied to blocks above *cut* (reorg safety)."""
        cut = int(cut)
        for key, _value in list(self._scan_prefix(kc.prefix_evm_logs())):
            if len(key) >= 9 and kc.unpack_u64(key[1:9]) > cut:
                self._raw_delete(key)
        for key, value in list(self._scan_prefix(kc.P_EVM_LOG_TX)):
            try:
                row = json.loads(value.decode("utf-8"))
                bh = int(row.get("block_height", 0) or 0)
            except Exception as exc:
                self._json_decode_failures += 1
                logger.warning(
                    "reorg purge: corrupt evm_log_tx JSON "
                    "(decode_failures=%s): %s",
                    self._json_decode_failures,
                    exc,
                )
                self._raw_delete(key)
                continue
            if bh > cut:
                self._raw_delete(key)
        for key, value in list(self._scan_prefix(kc.prefix_tx_prop_all())):
            try:
                row = json.loads(value.decode("utf-8"))
                bh = int(row.get("block_height", 0) or 0)
            except Exception as exc:
                self._json_decode_failures += 1
                logger.warning(
                    "reorg purge: corrupt tx_propagation JSON "
                    "(decode_failures=%s): %s",
                    self._json_decode_failures,
                    exc,
                )
                self._raw_delete(key)
                continue
            if bh > cut:
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

    def get_state_root_mismatches(self, limit: int = 20) -> List[Dict]:
        limit = max(1, min(int(limit), 100))
        rows: List[Dict] = []
        for _key, value in self._scan_prefix(kc.P_STATE_ROOT_MM, limit=limit * 4):
            try:
                rows.append(json.loads(value.decode("utf-8")))
            except Exception as exc:
                self._json_decode_failures += 1
                logger.warning(
                    "[RocksStore] corrupt state_root_mismatch row skipped "
                    "(decode_failures=%s): %s",
                    self._json_decode_failures,
                    exc,
                )
                continue
        rows.sort(key=lambda r: int(r.get("created_at", 0) or 0), reverse=True)
        return rows[:limit]

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
        key = kc.key_tx_prop(tx_hash, stage)
        self._raw_put(key, json.dumps(row).encode("utf-8"))

    def _decode_tx_propagation_event(self, raw: bytes) -> Optional[Dict]:
        row = self._loads_json_or_none(raw, context="tx_propagation")
        if row is None:
            return None
        detail = row.get("detail") or {}
        if isinstance(detail, str):
            try:
                detail = json.loads(detail)
            except Exception as exc:
                self._json_decode_failures += 1
                logger.warning(
                    "[RocksStore] corrupt tx_propagation detail "
                    "(decode_failures=%s): %s",
                    self._json_decode_failures,
                    exc,
                )
                detail = {}
        if not isinstance(detail, dict):
            detail = {}
        return {
            "stage": row.get("stage", ""),
            "node_id": row.get("node_id", ""),
            "peer_id": row.get("peer_id", ""),
            "block_height": int(row.get("block_height", 0) or 0),
            "detail": detail,
            "timestamp": int(row.get("created_at", 0) or 0),
        }

    def _tx_propagation_status(
        self,
        events: List[Dict],
        receipt: Optional[Dict],
        tx_row: Optional[Dict],
    ) -> str:
        stages = [e.get("stage", "") for e in events]
        if receipt or tx_row:
            return "confirmed"
        if "block_included" in stages:
            return "included"
        if "mempool_local" in stages or "mempool_remote" in stages:
            return "mempool"
        if events:
            return "propagating"
        return "unknown"

    def get_tx_propagation_trace(self, tx_hash: str) -> Dict:
        events = [
            ev
            for ev in (
                self._decode_tx_propagation_event(value)
                for _key, value in self._scan_prefix(kc.prefix_tx_prop(tx_hash), limit=500)
            )
            if ev is not None
        ]
        events.sort(key=lambda e: int(e.get("timestamp", 0) or 0))
        receipt = self.get_tx_receipt(tx_hash)
        tx_row = self.get_transaction(tx_hash)
        return {
            "tx_hash": tx_hash,
            "status": self._tx_propagation_status(events, receipt, tx_row),
            "events": events,
            "receipt": receipt,
            "transaction": tx_row,
        }

    def get_recent_tx_propagation(self, limit: int = 20) -> List[Dict]:
        limit = max(1, min(int(limit), 100))
        last_ts: dict[str, int] = {}
        for _key, value in self._scan_prefix(kc.prefix_tx_prop_all(), limit=50_000):
            try:
                row = json.loads(value.decode("utf-8"))
            except Exception as exc:
                self._json_decode_failures += 1
                logger.warning("rocks tx-prop JSON decode failed: %s", exc)
                continue
            th = str(row.get("tx_hash") or "")
            if not th:
                continue
            ts = int(row.get("created_at", 0) or 0)
            last_ts[th] = max(last_ts.get(th, 0), ts)
        ordered = sorted(last_ts.items(), key=lambda item: item[1], reverse=True)[:limit]
        return [self.get_tx_propagation_trace(tx_hash) for tx_hash, _ in ordered]

    def get_stats(self) -> Dict:
        stats = {
            "height": self.get_chain_tip(),
            "total_transactions": len(self._scan_prefix(kc.P_TX)),
            "total_accounts": len(self._scan_prefix(kc.prefix_accounts())),
            "total_burned": self.get_total_burned(),
            "total_supply": self.get_total_supply(),
            "engine": self.engine,
            "json_decode_failures": int(self._json_decode_failures),
            "rocksdb_tuning": {
                "block_cache_mb": self.block_cache_mb,
                "write_buffer_mb": self.write_buffer_mb,
                "sync": self.synchronous,
                "column_families": self.column_families,
                # Must live under rocksdb_tuning so /metrics emits abs_rocksdb_json_decode_failures.
                "json_decode_failures": int(self._json_decode_failures),
            },
        }
        if hasattr(self._engine, "storage_properties"):
            try:
                stats["rocksdb_properties"] = dict(self._engine.storage_properties())
            except Exception as exc:
                logger.warning("rocks get_stats storage_properties failed: %s", exc)
                stats["rocksdb_properties_error"] = str(exc)
        if hasattr(self._engine, "tuning_config"):
            try:
                stats["rocksdb_tuning"].update(dict(self._engine.tuning_config()))
            except Exception as exc:
                logger.warning("rocks get_stats tuning_config failed: %s", exc)
                stats["rocksdb_tuning_error"] = str(exc)
        return stats

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

    def _decode_evm_log_row(self, raw: bytes) -> Optional[Dict]:
        row = self._loads_json_or_none(raw, context="evm_log")
        if row is None:
            return None
        topics = row.get("topics", [])
        if isinstance(topics, str):
            try:
                topics = json.loads(topics)
            except Exception as exc:
                self._json_decode_failures += 1
                logger.warning(
                    "[RocksStore] corrupt evm_log topics "
                    "(decode_failures=%s): %s",
                    self._json_decode_failures,
                    exc,
                )
                topics = []
        row["topics"] = topics if isinstance(topics, list) else []
        return row

    def save_evm_logs(
        self,
        contract_address: str,
        logs: List[Dict],
        block_height: int = 0,
        tx_hash: str = "",
        timestamp: int = 0,
    ) -> int:
        if not logs:
            return 0
        ts = int(timestamp or time.time())
        saved = 0
        with self.atomic():
            for i, entry in enumerate(logs):
                topics = entry.get("topics", [])
                if not isinstance(topics, list):
                    topics = []
                row = {
                    "contract_address": contract_address,
                    "block_height": int(block_height),
                    "tx_hash": tx_hash or "",
                    "log_index": int(i),
                    "topics": topics,
                    "data": str(entry.get("data", "")),
                    "timestamp": ts,
                }
                payload = json.dumps(row, ensure_ascii=False).encode("utf-8")
                self._raw_put(kc.key_evm_log(block_height, tx_hash, i), payload)
                self._raw_put(kc.key_evm_log_tx(tx_hash, i), payload)
                saved += 1
        return saved

    def get_evm_logs(self, contract_address: str = "", limit: int = 100) -> List[Dict]:
        return self.query_evm_logs(
            addresses=[contract_address] if contract_address else None,
            limit=limit,
        )

    def get_evm_logs_by_tx(self, tx_hash: str) -> List[Dict]:
        if not tx_hash:
            return []
        rows = self._scan_prefix(kc.prefix_evm_logs_tx(tx_hash), limit=10_000)
        logs = [
            row
            for row in (self._decode_evm_log_row(val) for _, val in rows)
            if row is not None
        ]
        logs.sort(key=lambda r: (int(r.get("log_index", 0) or 0), int(r.get("block_height", 0) or 0)))
        return logs

    def query_evm_logs(
        self,
        from_block: int = 0,
        to_block: Optional[int] = None,
        addresses: Optional[List[str]] = None,
        topics: Optional[List] = None,
        limit: int = 10_000,
    ) -> List[Dict]:
        to_block = 2**63 - 1 if to_block is None else int(to_block)
        from_block = max(0, int(from_block))
        limit = max(1, min(int(limit), 10_000))
        addr_set = None
        if addresses:
            addr_set = {kc.normalize_address_key(a) for a in addresses if a}
        rows = self._scan_prefix(kc.prefix_evm_logs(), limit=50_000)
        out: List[Dict] = []
        for _, val in rows:
            row = self._decode_evm_log_row(val)
            if row is None:
                continue
            bh = int(row.get("block_height", 0) or 0)
            if bh < from_block or bh > to_block:
                continue
            if addr_set and kc.normalize_address_key(row.get("contract_address", "")) not in addr_set:
                continue
            if topics and not SqliteDatabase._evm_log_topics_match(row.get("topics") or [], topics):
                continue
            out.append(row)
            if len(out) >= limit:
                break
        out.sort(key=lambda r: (int(r.get("block_height", 0) or 0), int(r.get("log_index", 0) or 0)))
        return out

    def _decode_nft_token(self, raw: bytes) -> Optional[Dict]:
        row = self._loads_json_or_none(raw, context="nft_token")
        if row is None:
            return None
        meta = row.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception as exc:
                self._json_decode_failures += 1
                logger.warning(
                    "[RocksStore] corrupt nft_token metadata "
                    "(decode_failures=%s): %s",
                    self._json_decode_failures,
                    exc,
                )
                meta = {}
        row["metadata"] = meta if isinstance(meta, dict) else {}
        row["for_sale"] = bool(row.get("for_sale"))
        return row

    def save_nft_token(self, token: Dict) -> None:
        tid = str(token.get("token_id", "") or "")
        if not tid:
            return
        row = {
            "token_id": tid,
            "name": token.get("name", ""),
            "description": token.get("description", ""),
            "image_url": token.get("image_url", ""),
            "owner": token.get("owner", ""),
            "creator": token.get("creator", ""),
            "price": float(token.get("price", 0) or 0),
            "for_sale": bool(token.get("for_sale")),
            "created_at": int(token.get("created_at", 0) or 0),
            "metadata": token.get("metadata") or {},
        }
        self._raw_put(
            kc.key_nft_token(tid),
            json.dumps(row, ensure_ascii=False).encode("utf-8"),
        )

    def get_nft_tokens(self) -> List[Dict]:
        rows = self._scan_prefix(kc.prefix_nft_tokens(), limit=50_000)
        out = [
            row
            for row in (self._decode_nft_token(val) for _, val in rows)
            if row is not None
        ]
        out.sort(key=lambda r: int(r.get("created_at", 0) or 0))
        return out

    def _decode_nft_offer(self, raw: bytes) -> Optional[Dict]:
        return self._loads_json_or_none(raw, context="nft_offer")

    def save_nft_offer(self, offer: Dict) -> None:
        oid = str(offer.get("offer_id", "") or "")
        if not oid:
            return
        row = dict(offer)
        row["offer_id"] = oid
        row["price"] = float(row.get("price", 0) or 0)
        row["expires_at"] = int(row.get("expires_at", 0) or 0)
        row["created_at"] = int(row.get("created_at", 0) or 0)
        self._raw_put(
            kc.key_nft_offer(oid),
            json.dumps(row, ensure_ascii=False).encode("utf-8"),
        )

    def get_nft_offers(self) -> List[Dict]:
        rows = self._scan_prefix(kc.prefix_nft_offers(), limit=50_000)
        out = [
            row
            for row in (self._decode_nft_offer(val) for _, val in rows)
            if row is not None
        ]
        out.sort(key=lambda r: int(r.get("created_at", 0) or 0), reverse=True)
        return out

    def _decode_nft_auction(self, raw: bytes) -> Optional[Dict]:
        return self._loads_json_or_none(raw, context="nft_auction")

    def save_nft_auction(self, auction: Dict) -> None:
        aid = str(auction.get("auction_id", "") or "")
        if not aid:
            return
        row = dict(auction)
        row["auction_id"] = aid
        row["ends_at"] = int(row.get("ends_at", 0) or 0)
        row["created_at"] = int(row.get("created_at", 0) or 0)
        self._raw_put(
            kc.key_nft_auction(aid),
            json.dumps(row, ensure_ascii=False).encode("utf-8"),
        )

    def get_nft_auctions(self) -> List[Dict]:
        rows = self._scan_prefix(kc.prefix_nft_auctions(), limit=50_000)
        out = [
            row
            for row in (self._decode_nft_auction(val) for _, val in rows)
            if row is not None
        ]
        out.sort(key=lambda r: int(r.get("created_at", 0) or 0), reverse=True)
        return out

    def _decode_nft_sale(self, raw: bytes) -> Optional[Dict]:
        row = self._loads_json_or_none(raw, context="nft_sale")
        if row is None:
            return None
        return {
            "token_id": row.get("token_id", ""),
            "from": row.get("from", row.get("from_addr", "")),
            "to": row.get("to", row.get("to_addr", "")),
            "price": float(row.get("price", 0) or 0),
            "type": row.get("type", row.get("sale_type", "buy")),
            "timestamp": int(row.get("timestamp", row.get("created_at", 0)) or 0),
        }

    def save_nft_sale(self, sale: Dict) -> None:
        created_at = int(sale.get("timestamp", sale.get("created_at", 0)) or time.time())
        seq = int(sale.get("id", 0) or 0)
        if seq <= 0:
            seq = int(self.get_meta("nft_sale_seq", 0) or 0) + 1
            self.set_meta("nft_sale_seq", seq)
        row = {
            "id": seq,
            "token_id": sale.get("token_id", ""),
            "from": sale.get("from", sale.get("from_addr", "")),
            "to": sale.get("to", sale.get("to_addr", "")),
            "price": float(sale.get("price", 0) or 0),
            "type": sale.get("type", sale.get("sale_type", "buy")),
            "timestamp": created_at,
            "created_at": created_at,
        }
        self._raw_put(
            kc.key_nft_sale(created_at, seq),
            json.dumps(row, ensure_ascii=False).encode("utf-8"),
        )

    def get_nft_sales(self, limit: int = 100) -> List[Dict]:
        rows = self._scan_prefix(kc.prefix_nft_sales(), limit=50_000)
        out = [
            row
            for row in (self._decode_nft_sale(val) for _, val in rows)
            if row is not None
        ]
        out.sort(key=lambda r: int(r.get("timestamp", 0) or 0), reverse=True)
        return out[: max(1, int(limit))]

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
