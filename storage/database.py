#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Absolute Blockchain — единый слой хранения данных.
Один SQLite-файл, WAL-режим, все таблицы.
"""

import sqlite3
import json
import os
import threading
import time
from contextlib import contextmanager
from typing import Optional, List, Dict, Any


class Database:
    """
    Центральная база данных узла.
    Один экземпляр на весь процесс — используется через self.db во всех модулях.
    """

    def __init__(self, db_path: str = "data/blockchain.db", synchronous: str = "NORMAL"):
        self.db_path = db_path
        self.synchronous = (synchronous or "NORMAL").upper()
        self.lock = threading.RLock()
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # доступ к полям по имени
        self._configure()

    # ── Инициализация ────────────────────────────────────────────────────────

    def _configure(self):
        """Настройка SQLite, создание таблиц и миграция старой схемы."""
        self.conn.execute("PRAGMA journal_mode=WAL")
        sync = self.synchronous if self.synchronous in ("OFF", "NORMAL", "FULL", "EXTRA") else "NORMAL"
        self.conn.execute(f"PRAGMA synchronous={sync}")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()
        self._migrate()
        self.conn.commit()

    def _migrate(self):
        """Добавляет недостающие колонки и переименовывает block_hash -> hash."""
        import json as _json

        # Читаем текущие колонки таблицы blocks
        cols_info = self.conn.execute("PRAGMA table_info(blocks)").fetchall()
        block_cols = {row[1] for row in cols_info}

        # ── 1. Переименование block_hash -> hash (старая схема) ──────────────
        if "block_hash" in block_cols and "hash" not in block_cols:
            # SQLite 3.25+ поддерживает RENAME COLUMN
            try:
                self.conn.execute("ALTER TABLE blocks RENAME COLUMN block_hash TO hash")
                block_cols.discard("block_hash")
                block_cols.add("hash")
                print("[DB] Migration: renamed 'block_hash' -> 'hash'")
            except Exception:
                # Fallback: добавляем колонку hash и копируем значения
                self.conn.execute("ALTER TABLE blocks ADD COLUMN hash TEXT DEFAULT ''")
                self.conn.execute("UPDATE blocks SET hash = block_hash")
                block_cols.add("hash")
                print("[DB] Migration: added 'hash' column (copied from block_hash)")

        # ── 2. Добавляем недостающие колонки ─────────────────────────────────
        add_cols = [
            ("blocks", "data",         "TEXT DEFAULT '{}'"),
            ("blocks", "tx_count",     "INTEGER DEFAULT 0"),
            ("blocks", "gas_used",     "INTEGER DEFAULT 0"),
            ("blocks", "total_burned", "REAL DEFAULT 0.0"),
            ("blocks", "extra_data",   "TEXT DEFAULT ''"),
            ("transactions", "burned",   "REAL NOT NULL DEFAULT 0.0"),
            ("transactions", "fee",      "REAL NOT NULL DEFAULT 0.0"),
            ("transactions", "gas_used", "INTEGER NOT NULL DEFAULT 21000"),
        ]
        existing: dict = {"blocks": block_cols}
        for table, col, col_def in add_cols:
            if table not in existing:
                c = self.conn.execute(f"PRAGMA table_info({table})")
                existing[table] = {row[1] for row in c.fetchall()}
            if col not in existing[table]:
                try:
                    self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
                    print(f"[DB] Migration: added '{table}.{col}'")
                    existing[table].add(col)
                except Exception as e:
                    print(f"[DB] Migration warning ({table}.{col}): {e}")

        # ── 3. Заполняем data для старых блоков ──────────────────────────────
        try:
            count = self.conn.execute(
                "SELECT COUNT(*) FROM blocks WHERE data='{}' OR data IS NULL OR data=''"
            ).fetchone()[0]
            if count > 0:
                rows = self.conn.execute(
                    "SELECT height, hash, parent_hash, timestamp, miner "
                    "FROM blocks WHERE data='{}' OR data IS NULL OR data=''"
                ).fetchall()
                for row in rows:
                    block_dict = {
                        "height": row[0], "hash": row[1] or "",
                        "parent_hash": row[2] or "", "timestamp": row[3] or 0,
                        "miner": row[4] or "genesis",
                        "tx_count": 0, "gas_used": 0,
                        "total_burned": 0.0, "extra_data": "legacy",
                        "transactions": [],
                    }
                    self.conn.execute(
                        "UPDATE blocks SET data=? WHERE height=?",
                        (_json.dumps(block_dict), row[0])
                    )
                print(f"[DB] Migration: backfilled 'data' for {count} old block(s)")
        except Exception as e:
            print(f"[DB] Migration backfill warning: {e}")

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS blocks (
                height       INTEGER PRIMARY KEY,
                hash         TEXT    UNIQUE NOT NULL,
                parent_hash  TEXT    NOT NULL,
                timestamp    INTEGER NOT NULL,
                miner        TEXT    NOT NULL,
                tx_count     INTEGER DEFAULT 0,
                gas_used     INTEGER DEFAULT 0,
                total_burned REAL    DEFAULT 0.0,
                extra_data   TEXT    DEFAULT '',
                data         TEXT    NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS transactions (
                hash         TEXT    PRIMARY KEY,
                block_height INTEGER NOT NULL,
                from_addr    TEXT    NOT NULL,
                to_addr      TEXT    NOT NULL,
                value        REAL    NOT NULL DEFAULT 0.0,
                gas          INTEGER NOT NULL DEFAULT 21000,
                gas_used     INTEGER NOT NULL DEFAULT 21000,
                fee          REAL    NOT NULL DEFAULT 0.0,
                burned       REAL    NOT NULL DEFAULT 0.0,
                nonce        INTEGER NOT NULL DEFAULT 0,
                tx_data      TEXT    DEFAULT '',
                status       INTEGER DEFAULT 1,
                timestamp    INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS accounts (
                address  TEXT    PRIMARY KEY,
                balance  REAL    NOT NULL DEFAULT 0.0,
                nonce    INTEGER NOT NULL DEFAULT 0,
                code     TEXT    DEFAULT NULL,
                storage  TEXT    DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS validators (
                address  TEXT    PRIMARY KEY,
                stake    REAL    NOT NULL DEFAULT 0.0,
                active   INTEGER DEFAULT 1,
                slashed  INTEGER DEFAULT 0,
                joined_at INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS checkpoints (
                epoch      INTEGER PRIMARY KEY,
                block_hash TEXT    NOT NULL,
                justified  INTEGER DEFAULT 0,
                finalized  INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS burn_stats (
                block_height  INTEGER PRIMARY KEY,
                burned_amount REAL    NOT NULL DEFAULT 0.0,
                total_burned  REAL    NOT NULL DEFAULT 0.0
            );

            CREATE TABLE IF NOT EXISTS bridge_locks (
                tx_hash    TEXT    PRIMARY KEY,
                from_addr  TEXT    NOT NULL,
                to_chain   TEXT    NOT NULL,
                to_addr    TEXT    NOT NULL,
                amount     REAL    NOT NULL,
                status     TEXT    DEFAULT 'pending',
                created_at INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_tx_block ON transactions(block_height);
            CREATE INDEX IF NOT EXISTS idx_tx_from  ON transactions(from_addr);
            CREATE INDEX IF NOT EXISTS idx_tx_to    ON transactions(to_addr);
            CREATE TABLE IF NOT EXISTS meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_blocks_ts ON blocks(timestamp);
        """)

    def initialize(self):
        """Публичный метод инициализации (вызывается из NodeOrchestrator)."""
        self._configure()

    # ── Блоки ────────────────────────────────────────────────────────────────

    def save_block(self, block: Dict) -> bool:
        with self.lock:
            try:
                self._insert_block(block)
                self.conn.commit()
                return True
            except Exception as e:
                self.conn.rollback()
                print(f"[DB] save_block error: {e}")
                return False

    def _insert_block(self, block: Dict) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO blocks
               (height, hash, parent_hash, timestamp, miner,
                tx_count, gas_used, total_burned, extra_data, data)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                block.get("height", block.get("number", 0)),
                block.get("hash", block.get("block_hash", "")),
                block.get("parent_hash", "0" * 64),
                block.get("timestamp", int(time.time())),
                block.get("miner", ""),
                block.get("tx_count", len(block.get("transactions", []))),
                block.get("gas_used", 0),
                block.get("total_burned", 0.0),
                block.get("extra_data", ""),
                json.dumps(block),
            ),
        )

    def persist_block_atomic(
        self,
        block: Dict,
        transactions: List[Dict],
        burned_amount: float = 0.0,
        burn_address: str = "",
    ) -> bool:
        """Атомарно сохраняет блок, транзакции и статистику сжигания."""
        with self.lock:
            try:
                self.conn.execute("BEGIN IMMEDIATE")
                self._persist_block_locked(block, transactions, burned_amount, burn_address)
                self.conn.commit()
                return True
            except Exception as e:
                self.conn.rollback()
                print(f"[DB] persist_block_atomic error: {e}")
                return False

    def _persist_block_locked(
        self,
        block: Dict,
        transactions: List[Dict],
        burned_amount: float = 0.0,
        burn_address: str = "",
    ) -> None:
        """Persist block + txs inside an open transaction (caller holds BEGIN)."""
        self._insert_block(block)
        for tx in transactions:
            self._insert_transaction(tx)
        if burned_amount > 0:
            self._insert_burn_record(block.get("height", 0), burned_amount)
            if burn_address:
                self._apply_balance_delta(burn_address, burned_amount)

    @contextmanager
    def atomic(self):
        """Single-writer SQLite transaction for block execution."""
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield self
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    def balance_delta(self, address: str, delta: float) -> None:
        """Balance change without commit (inside atomic())."""
        self._apply_balance_delta(address, delta)

    def nonce_increment(self, address: str) -> int:
        """Nonce bump without commit (inside atomic())."""
        self.conn.execute(
            """INSERT INTO accounts (address, balance, nonce) VALUES (?,0,1)
               ON CONFLICT(address) DO UPDATE SET nonce=nonce+1""",
            (address,),
        )
        row = self.conn.execute(
            "SELECT nonce FROM accounts WHERE address=?", (address,)
        ).fetchone()
        return int(row["nonce"]) if row else 1

    def get_all_accounts(self) -> List[Dict]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT address, balance, nonce FROM accounts ORDER BY address"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_block(self, height: int) -> Optional[Dict]:
        with self.lock:
            row = self.conn.execute(
                "SELECT data FROM blocks WHERE height=?", (height,)
            ).fetchone()
            return json.loads(row["data"]) if row else None

    def get_block_by_hash(self, block_hash: str) -> Optional[Dict]:
        with self.lock:
            row = self.conn.execute(
                "SELECT data FROM blocks WHERE hash=?", (block_hash,)
            ).fetchone()
            return json.loads(row["data"]) if row else None

    def get_latest_blocks(self, limit: int = 20) -> List[Dict]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT data FROM blocks ORDER BY height DESC LIMIT ?", (limit,)
            ).fetchall()
            return [json.loads(r["data"]) for r in rows]

    def get_chain_tip(self) -> int:
        """Возвращает высоту последнего блока (0 если цепь пуста)."""
        with self.lock:
            row = self.conn.execute(
                "SELECT COALESCE(MAX(height),0) as h FROM blocks"
            ).fetchone()
            return row["h"] if row else 0

    def get_last_block(self) -> Optional[Dict]:
        with self.lock:
            row = self.conn.execute(
                "SELECT data FROM blocks ORDER BY height DESC LIMIT 1"
            ).fetchone()
            return json.loads(row["data"]) if row else None

    def truncate_blocks_above(self, height: int) -> int:
        """Remove blocks with height > given tip (for P2P fork resync). Returns deleted count."""
        with self.atomic():
            cur = self.conn.execute(
                "DELETE FROM blocks WHERE height > ?", (int(height),)
            )
            return cur.rowcount

    def truncate_all_blocks(self) -> int:
        """Remove entire chain (used when joining peer with different genesis)."""
        with self.atomic():
            cur = self.conn.execute("DELETE FROM blocks")
            return cur.rowcount

    # ── Транзакции ───────────────────────────────────────────────────────────

    def _insert_transaction(self, tx: Dict) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO transactions
               (hash, block_height, from_addr, to_addr, value,
                gas, gas_used, fee, burned, nonce, tx_data, status, timestamp)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                tx.get("hash", tx.get("tx_hash", "")),
                tx.get("block_height", 0),
                tx.get("from_addr", tx.get("from", "")),
                tx.get("to_addr", tx.get("to", "")),
                tx.get("value", tx.get("amount", 0.0)),
                tx.get("gas", 21000),
                tx.get("gas_used", tx.get("gas", 21000)),
                tx.get("fee", 0.0),
                tx.get("burned", 0.0),
                tx.get("nonce", 0),
                tx.get("data", tx.get("tx_data", "")),
                tx.get("status", 1),
                tx.get("timestamp", int(time.time())),
            ),
        )

    def save_transaction(self, tx: Dict) -> bool:
        with self.lock:
            try:
                self._insert_transaction(tx)
                self.conn.commit()
                return True
            except Exception as e:
                self.conn.rollback()
                print(f"[DB] save_transaction error: {e}")
                return False

    def get_transaction(self, tx_hash: str) -> Optional[Dict]:
        with self.lock:
            row = self.conn.execute(
                "SELECT * FROM transactions WHERE hash=?", (tx_hash,)
            ).fetchone()
            return dict(row) if row else None

    def get_transactions_by_address(self, address: str, limit: int = 50) -> List[Dict]:
        with self.lock:
            rows = self.conn.execute(
                """SELECT * FROM transactions
                   WHERE from_addr=? OR to_addr=?
                   ORDER BY block_height DESC LIMIT ?""",
                (address, address, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_transactions_in_block(self, height: int) -> List[Dict]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM transactions WHERE block_height=?", (height,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Аккаунты / балансы ───────────────────────────────────────────────────

    def get_balance(self, address: str) -> float:
        with self.lock:
            row = self.conn.execute(
                "SELECT balance FROM accounts WHERE address=?", (address,)
            ).fetchone()
            return float(row["balance"]) if row else 0.0

    def _apply_balance_delta(self, address: str, delta: float) -> None:
        self.conn.execute(
            """INSERT INTO accounts (address, balance, nonce)
               VALUES (?, MAX(0.0, ?), 0)
               ON CONFLICT(address) DO UPDATE
               SET balance = MAX(0.0, balance + ?)""",
            (address, delta, delta),
        )

    def update_balance(self, address: str, delta: float) -> float:
        """Изменяет баланс на delta (может быть отрицательным). Возвращает новый баланс."""
        with self.lock:
            self._apply_balance_delta(address, delta)
            self.conn.commit()
            return self.get_balance(address)

    def set_balance(self, address: str, balance: float) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT INTO accounts (address, balance) VALUES (?,?)
                   ON CONFLICT(address) DO UPDATE SET balance=excluded.balance""",
                (address, balance),
            )
            self.conn.commit()

    def get_nonce(self, address: str) -> int:
        with self.lock:
            row = self.conn.execute(
                "SELECT nonce FROM accounts WHERE address=?", (address,)
            ).fetchone()
            return row["nonce"] if row else 0

    def increment_nonce(self, address: str) -> int:
        with self.lock:
            self.conn.execute(
                """INSERT INTO accounts (address, balance, nonce) VALUES (?,0,1)
                   ON CONFLICT(address) DO UPDATE SET nonce=nonce+1""",
                (address,),
            )
            self.conn.commit()
            return self.get_nonce(address)

    def get_account(self, address: str) -> Optional[Dict]:
        with self.lock:
            row = self.conn.execute(
                "SELECT * FROM accounts WHERE address=?", (address,)
            ).fetchone()
            return dict(row) if row else None

    def save_account(self, address: str, balance: float = 0.0,
                     nonce: int = 0, code: str = None, storage: str = None) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT INTO accounts (address, balance, nonce, code, storage)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT(address) DO UPDATE
                   SET balance=excluded.balance, nonce=excluded.nonce,
                       code=excluded.code, storage=excluded.storage""",
                (address, balance, nonce, code, storage),
            )
            self.conn.commit()

    def update_account_storage(self, address: str, storage: Dict) -> None:
        with self.lock:
            self.conn.execute(
                "UPDATE accounts SET storage=? WHERE address=?",
                (json.dumps(storage), address),
            )
            self.conn.commit()

    # ── Валидаторы ───────────────────────────────────────────────────────────

    def save_validator(self, address: str, stake: float) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT INTO validators (address, stake, joined_at)
                   VALUES (?,?,?)
                   ON CONFLICT(address) DO UPDATE SET stake=excluded.stake""",
                (address, stake, int(time.time())),
            )
            self.conn.commit()

    def get_validators(self, active_only: bool = True) -> List[Dict]:
        with self.lock:
            query = "SELECT * FROM validators"
            if active_only:
                query += " WHERE active=1 AND slashed=0"
            rows = self.conn.execute(query).fetchall()
            return [dict(r) for r in rows]

    def slash_validator(self, address: str) -> None:
        with self.lock:
            self.conn.execute(
                "UPDATE validators SET slashed=1, active=0 WHERE address=?", (address,)
            )
            self.conn.commit()

    # ── Финальность (Casper FFG) ─────────────────────────────────────────────

    def save_checkpoint(self, epoch: int, block_hash: str,
                        justified: bool = False, finalized: bool = False) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT INTO checkpoints (epoch, block_hash, justified, finalized)
                   VALUES (?,?,?,?)
                   ON CONFLICT(epoch) DO UPDATE
                   SET justified=excluded.justified, finalized=excluded.finalized""",
                (epoch, block_hash, int(justified), int(finalized)),
            )
            self.conn.commit()

    def get_checkpoint(self, epoch: int) -> Optional[Dict]:
        with self.lock:
            row = self.conn.execute(
                "SELECT * FROM checkpoints WHERE epoch=?", (epoch,)
            ).fetchone()
            return dict(row) if row else None

    # ── Сжигание токенов ─────────────────────────────────────────────────────

    def _insert_burn_record(self, block_height: int, burned_amount: float) -> None:
        prev = self.conn.execute(
            "SELECT COALESCE(MAX(total_burned),0) as tb FROM burn_stats"
        ).fetchone()
        total = float(prev["tb"]) + burned_amount
        self.conn.execute(
            """INSERT OR REPLACE INTO burn_stats (block_height, burned_amount, total_burned)
               VALUES (?,?,?)""",
            (block_height, burned_amount, total),
        )

    def record_burn(self, block_height: int, burned_amount: float) -> None:
        with self.lock:
            self._insert_burn_record(block_height, burned_amount)
            self.conn.commit()

    def get_total_burned(self) -> float:
        with self.lock:
            row = self.conn.execute(
                "SELECT COALESCE(MAX(total_burned),0) as tb FROM burn_stats"
            ).fetchone()
            return float(row["tb"]) if row else 0.0

    def get_burn_stats(self) -> Dict:
        with self.lock:
            row = self.conn.execute(
                """SELECT COUNT(*) as blocks_with_burn,
                          COALESCE(SUM(burned_amount),0) as total,
                          COALESCE(AVG(burned_amount),0) as avg_per_block
                   FROM burn_stats"""
            ).fetchone()
            return {
                "total_burned": float(row["total"]),
                "avg_per_block": float(row["avg_per_block"]),
                "blocks_with_burn": int(row["blocks_with_burn"]),
            }

    # ── Мост (Cross-chain) ───────────────────────────────────────────────────

    def save_bridge_lock(self, from_addr: str, to_chain: str, to_addr: str,
                         amount: float, tx_hash: str) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO bridge_locks
                   (tx_hash, from_addr, to_chain, to_addr, amount, status, created_at)
                   VALUES (?,?,?,?,?,'pending',?)""",
                (tx_hash, from_addr, to_chain, to_addr, amount, int(time.time())),
            )
            self.conn.commit()

    def confirm_bridge_lock(self, tx_hash: str) -> None:
        with self.lock:
            self.conn.execute(
                "UPDATE bridge_locks SET status='confirmed' WHERE tx_hash=?", (tx_hash,)
            )
            self.conn.commit()

    def get_bridge_locks(self, limit: int = 50) -> List[Dict]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM bridge_locks ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Метаданные (токеномика, конфиг) ─────────────────────────────────────

    def set_meta(self, key: str, value: Any) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                (key, json.dumps(value, ensure_ascii=False)),
            )
            self.conn.commit()

    def get_meta(self, key: str, default: Any = None) -> Any:
        with self.lock:
            row = self.conn.execute(
                "SELECT value FROM meta WHERE key=?", (key,)
            ).fetchone()
            if not row:
                return default
            try:
                return json.loads(row["value"])
            except Exception:
                return row["value"]

    def get_total_supply(self) -> float:
        """Сумма всех балансов аккаунтов."""
        with self.lock:
            row = self.conn.execute(
                "SELECT COALESCE(SUM(balance), 0) as total FROM accounts"
            ).fetchone()
            return float(row["total"] if row else 0)

    # ── Статистика ───────────────────────────────────────────────────────────

    def get_stats(self) -> Dict:
        with self.lock:
            height = self.get_chain_tip()
            tx_count = self.conn.execute(
                "SELECT COUNT(*) as c FROM transactions"
            ).fetchone()["c"]
            account_count = self.conn.execute(
                "SELECT COUNT(*) as c FROM accounts"
            ).fetchone()["c"]
            return {
                "height": height,
                "total_transactions": tx_count,
                "total_accounts": account_count,
                "total_burned": self.get_total_burned(),
                "total_supply": self.get_total_supply(),
            }

    # ── Утилиты ──────────────────────────────────────────────────────────────

    def backup_to(self, dest_path: str) -> bool:
        """Online-бэкап SQLite через встроенный backup API."""
        with self.lock:
            dest_dir = os.path.dirname(dest_path)
            if dest_dir:
                os.makedirs(dest_dir, exist_ok=True)
            try:
                dest = sqlite3.connect(dest_path)
                self.conn.backup(dest)
                dest.close()
                return True
            except Exception as e:
                print(f"[DB] backup_to error: {e}")
                return False

    def close(self):
        with self.lock:
            self.conn.close()


class BlockchainDB(Database):
    """Legacy API used by v47 tests."""

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def get_latest_block_number(self) -> int:
        return self.get_chain_tip()

    def get_block(self, block_hash: str) -> Optional[Dict]:
        return self.get_block_by_hash(block_hash)

    def save_metadata(self, key: str, value: Any) -> None:
        self.set_meta(key, value)

    def get_metadata(self, key: str, default: Any = None) -> Any:
        return self.get_meta(key, default)

    def get_stats(self) -> Dict:
        stats = super().get_stats()
        stats["total_blocks"] = stats.get("height", 0)
        return stats
