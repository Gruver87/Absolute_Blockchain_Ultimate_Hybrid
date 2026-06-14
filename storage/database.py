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
            ("accounts", "code",     "TEXT DEFAULT NULL"),
            ("accounts", "storage",  "TEXT DEFAULT NULL"),
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

            CREATE TABLE IF NOT EXISTS bridge_credits (
                credit_key  TEXT PRIMARY KEY,
                l1_tx_hash  TEXT NOT NULL,
                recipient   TEXT NOT NULL,
                amount      REAL NOT NULL,
                from_chain  TEXT NOT NULL,
                credited_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS minivm_contracts (
                address     TEXT PRIMARY KEY,
                bytecode    TEXT NOT NULL,
                storage     TEXT NOT NULL DEFAULT '{}',
                deployed_at INTEGER NOT NULL DEFAULT 0,
                calls       INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS slash_events (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                validator  TEXT NOT NULL,
                reason     TEXT NOT NULL,
                epoch      INTEGER NOT NULL DEFAULT 0,
                penalty    INTEGER NOT NULL DEFAULT 0,
                timestamp  INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS evm_logs (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_address TEXT NOT NULL,
                block_height     INTEGER NOT NULL DEFAULT 0,
                tx_hash          TEXT NOT NULL DEFAULT '',
                log_index        INTEGER NOT NULL DEFAULT 0,
                topics           TEXT NOT NULL DEFAULT '[]',
                data             TEXT NOT NULL DEFAULT '',
                timestamp        INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_evm_logs_contract ON evm_logs(contract_address);

            CREATE TABLE IF NOT EXISTS oracle_feeds (
                feed_id       TEXT PRIMARY KEY,
                symbol        TEXT NOT NULL,
                value         REAL NOT NULL,
                source        TEXT NOT NULL DEFAULT '',
                reporter      TEXT NOT NULL DEFAULT '',
                signature     TEXT NOT NULL DEFAULT '',
                payload       TEXT NOT NULL DEFAULT '{}',
                block_height  INTEGER NOT NULL DEFAULT 0,
                submitted_at  INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_oracle_feeds_symbol ON oracle_feeds(symbol);
            CREATE INDEX IF NOT EXISTS idx_oracle_feeds_ts ON oracle_feeds(submitted_at);

            CREATE TABLE IF NOT EXISTS lightning_channels (
                channel_id   TEXT PRIMARY KEY,
                node1        TEXT NOT NULL,
                node2        TEXT NOT NULL,
                capacity     REAL NOT NULL,
                balance1     REAL NOT NULL,
                balance2     REAL NOT NULL,
                status       TEXT NOT NULL DEFAULT 'open',
                fee_rate     REAL NOT NULL DEFAULT 0.00001,
                created_at   INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS lightning_payments (
                payment_id   TEXT PRIMARY KEY,
                channel_id   TEXT NOT NULL,
                from_node    TEXT NOT NULL,
                to_node      TEXT NOT NULL,
                amount       REAL NOT NULL,
                fee          REAL NOT NULL DEFAULT 0,
                status       TEXT NOT NULL DEFAULT 'completed',
                payment_hash TEXT NOT NULL DEFAULT '',
                timestamp    INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_ln_payments_channel ON lightning_payments(channel_id);

            CREATE TABLE IF NOT EXISTS plasma_deposits (
                deposit_id    TEXT PRIMARY KEY,
                from_addr     TEXT NOT NULL,
                amount        REAL NOT NULL,
                main_tx_hash  TEXT NOT NULL DEFAULT '',
                created_at    INTEGER NOT NULL DEFAULT 0,
                status        TEXT NOT NULL DEFAULT 'confirmed'
            );

            CREATE TABLE IF NOT EXISTS plasma_blocks (
                block_id      INTEGER PRIMARY KEY,
                block_hash    TEXT NOT NULL,
                parent_hash   TEXT NOT NULL,
                transactions  TEXT NOT NULL DEFAULT '[]',
                total_amount  REAL NOT NULL DEFAULT 0,
                tx_count      INTEGER NOT NULL DEFAULT 0,
                created_at    INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS plasma_exits (
                exit_id     TEXT PRIMARY KEY,
                deposit_id  TEXT NOT NULL,
                user_addr   TEXT NOT NULL,
                amount      REAL NOT NULL,
                created_at  INTEGER NOT NULL DEFAULT 0,
                status      TEXT NOT NULL DEFAULT 'pending'
            );

            CREATE TABLE IF NOT EXISTS crypto_wills (
                will_id         TEXT PRIMARY KEY,
                owner           TEXT NOT NULL,
                heir            TEXT NOT NULL,
                amount          REAL NOT NULL,
                assets          TEXT NOT NULL DEFAULT '{}',
                execution_time  INTEGER NOT NULL DEFAULT 0,
                created_at      INTEGER NOT NULL DEFAULT 0,
                status          TEXT NOT NULL DEFAULT 'pending',
                witnesses       TEXT NOT NULL DEFAULT '[]'
            );
            CREATE INDEX IF NOT EXISTS idx_crypto_wills_owner ON crypto_wills(owner);
            CREATE INDEX IF NOT EXISTS idx_crypto_wills_status ON crypto_wills(status);

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
                "SELECT address, balance, nonce, code, storage FROM accounts ORDER BY address"
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

    def truncate_chain_state(self, height: int) -> int:
        """Remove blocks, txs, and burn stats above height."""
        with self.atomic():
            self.conn.execute(
                "DELETE FROM transactions WHERE block_height > ?", (int(height),)
            )
            self.conn.execute(
                "DELETE FROM burn_stats WHERE block_height > ?", (int(height),)
            )
            cur = self.conn.execute(
                "DELETE FROM blocks WHERE height > ?", (int(height),)
            )
            return cur.rowcount

    def reset_accounts_from_alloc(self, alloc: Dict[str, float]) -> None:
        """Reset all account balances/nonces from genesis allocation map."""
        with self.atomic():
            self.conn.execute("DELETE FROM accounts")
            for addr, amount in alloc.items():
                self.conn.execute(
                    "INSERT INTO accounts (address, balance, nonce) VALUES (?, ?, 0)",
                    (addr, float(amount)),
                )

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

    def get_recent_transactions(self, limit: int = 30) -> List[Dict]:
        """Последние транзакции по всей цепи (для dashboard/explorer)."""
        with self.lock:
            rows = self.conn.execute(
                """SELECT * FROM transactions
                   ORDER BY block_height DESC, rowid DESC LIMIT ?""",
                (limit,),
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

    def bridge_credit_key(self, l1_tx_hash: str, recipient: str, amount: float, from_chain: str) -> str:
        import hashlib
        raw = f"{l1_tx_hash}:{recipient}:{amount}:{from_chain}".lower()
        return hashlib.sha256(raw.encode()).hexdigest()

    def has_bridge_credit(self, credit_key: str) -> bool:
        with self.lock:
            row = self.conn.execute(
                "SELECT 1 FROM bridge_credits WHERE credit_key=?", (credit_key,)
            ).fetchone()
            return row is not None

    def save_bridge_credit(self, l1_tx_hash: str, recipient: str, amount: float, from_chain: str) -> str:
        key = self.bridge_credit_key(l1_tx_hash, recipient, amount, from_chain)
        with self.lock:
            self.conn.execute(
                """INSERT OR IGNORE INTO bridge_credits
                   (credit_key, l1_tx_hash, recipient, amount, from_chain, credited_at)
                   VALUES (?,?,?,?,?,?)""",
                (key, l1_tx_hash, recipient, amount, from_chain, int(time.time())),
            )
            self.conn.commit()
        return key

    def save_minivm_contract(self, address: str, bytecode: list, storage: dict, calls: int = 0) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO minivm_contracts
                   (address, bytecode, storage, deployed_at, calls)
                   VALUES (?,?,?,?,?)""",
                (
                    address,
                    json.dumps(bytecode, ensure_ascii=False),
                    json.dumps(storage, ensure_ascii=False),
                    int(time.time()),
                    calls,
                ),
            )
            self.conn.commit()

    def load_minivm_contracts(self) -> List[Dict]:
        with self.lock:
            rows = self.conn.execute("SELECT * FROM minivm_contracts").fetchall()
            out = []
            for row in rows:
                item = dict(row)
                try:
                    item["bytecode"] = json.loads(item.get("bytecode") or "[]")
                    item["storage"] = json.loads(item.get("storage") or "{}")
                except Exception:
                    item["bytecode"] = []
                    item["storage"] = {}
                out.append(item)
            return out

    def save_slash_event(self, validator: str, reason: str, epoch: int, penalty: int) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT INTO slash_events (validator, reason, epoch, penalty, timestamp)
                   VALUES (?,?,?,?,?)""",
                (validator, reason, epoch, penalty, int(time.time())),
            )
            self.conn.execute(
                "UPDATE validators SET slashed=1, active=0 WHERE address=?",
                (validator,),
            )
            self.conn.commit()

    def get_slash_events(self, limit: int = 100) -> List[Dict]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM slash_events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def save_evm_logs(
        self,
        contract_address: str,
        logs: List[Dict],
        block_height: int = 0,
        tx_hash: str = "",
        timestamp: int = 0,
    ) -> int:
        """Persist EVM event logs emitted during contract execution."""
        if not logs:
            return 0
        import time as _time
        ts = int(timestamp or _time.time())
        saved = 0
        with self.lock:
            base_idx = self.conn.execute(
                "SELECT COUNT(*) AS c FROM evm_logs WHERE contract_address=?",
                (contract_address,),
            ).fetchone()["c"]
            for i, entry in enumerate(logs):
                topics = entry.get("topics", [])
                if isinstance(topics, list):
                    topics_json = json.dumps(topics)
                else:
                    topics_json = "[]"
                data = entry.get("data", "")
                self.conn.execute(
                    """INSERT INTO evm_logs
                       (contract_address, block_height, tx_hash, log_index, topics, data, timestamp)
                       VALUES (?,?,?,?,?,?,?)""",
                    (
                        contract_address,
                        int(block_height),
                        tx_hash or "",
                        int(base_idx) + i,
                        topics_json,
                        str(data),
                        ts,
                    ),
                )
                saved += 1
            self.conn.commit()
        return saved

    def get_evm_logs(
        self,
        contract_address: str = "",
        limit: int = 100,
    ) -> List[Dict]:
        with self.lock:
            if contract_address:
                rows = self.conn.execute(
                    """SELECT * FROM evm_logs WHERE contract_address=?
                       ORDER BY id DESC LIMIT ?""",
                    (contract_address, int(limit)),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    "SELECT * FROM evm_logs ORDER BY id DESC LIMIT ?",
                    (int(limit),),
                ).fetchall()
            out = []
            for r in rows:
                item = dict(r)
                try:
                    item["topics"] = json.loads(item.get("topics") or "[]")
                except Exception:
                    item["topics"] = []
                out.append(item)
            return out

    def save_oracle_feed(
        self,
        feed_id: str,
        symbol: str,
        value: float,
        source: str = "",
        reporter: str = "",
        signature: str = "",
        payload: str = "{}",
        block_height: int = 0,
        submitted_at: int = 0,
    ) -> None:
        import time as _time
        with self.lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO oracle_feeds
                   (feed_id, symbol, value, source, reporter, signature,
                    payload, block_height, submitted_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    feed_id,
                    symbol,
                    float(value),
                    source,
                    reporter,
                    signature,
                    payload,
                    int(block_height),
                    int(submitted_at or _time.time()),
                ),
            )
            self.conn.commit()

    def get_oracle_feeds(self, symbol: str = "", limit: int = 50) -> List[Dict]:
        with self.lock:
            if symbol:
                rows = self.conn.execute(
                    """SELECT * FROM oracle_feeds WHERE symbol=?
                       ORDER BY submitted_at DESC LIMIT ?""",
                    (symbol.lower(), int(limit)),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    "SELECT * FROM oracle_feeds ORDER BY submitted_at DESC LIMIT ?",
                    (int(limit),),
                ).fetchall()
            return [dict(r) for r in rows]

    # ── Lightning Network (Wave 40 persistence) ─────────────────────────────

    def save_lightning_channel(self, ch: Dict) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO lightning_channels
                   (channel_id, node1, node2, capacity, balance1, balance2,
                    status, fee_rate, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    ch["channel_id"],
                    ch["node1"],
                    ch["node2"],
                    float(ch["capacity"]),
                    float(ch["balance1"]),
                    float(ch["balance2"]),
                    ch.get("status", "open"),
                    float(ch.get("fee_rate", 0.00001)),
                    int(ch.get("created_at", 0)),
                ),
            )
            self.conn.commit()

    def get_lightning_channels(self, status: str = "") -> List[Dict]:
        with self.lock:
            if status:
                rows = self.conn.execute(
                    "SELECT * FROM lightning_channels WHERE status=? ORDER BY created_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    "SELECT * FROM lightning_channels ORDER BY created_at DESC"
                ).fetchall()
            return [dict(r) for r in rows]

    def save_lightning_payment(self, p: Dict) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO lightning_payments
                   (payment_id, channel_id, from_node, to_node, amount, fee,
                    status, payment_hash, timestamp)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    p["payment_id"],
                    p["channel_id"],
                    p["from_node"],
                    p["to_node"],
                    float(p["amount"]),
                    float(p.get("fee", 0)),
                    p.get("status", "completed"),
                    p.get("payment_hash", ""),
                    int(p.get("timestamp", 0)),
                ),
            )
            self.conn.commit()

    def get_lightning_payments(self, limit: int = 50) -> List[Dict]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM lightning_payments ORDER BY timestamp DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Plasma L2 (Wave 40 persistence) ─────────────────────────────────────

    def save_plasma_deposit(self, dep: Dict) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO plasma_deposits
                   (deposit_id, from_addr, amount, main_tx_hash, created_at, status)
                   VALUES (?,?,?,?,?,?)""",
                (
                    dep["id"],
                    dep["from"],
                    float(dep["amount"]),
                    dep.get("main_tx_hash", ""),
                    int(dep.get("created_at", 0)),
                    dep.get("status", "confirmed"),
                ),
            )
            self.conn.commit()

    def get_plasma_deposits(self, limit: int = 200) -> List[Dict]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM plasma_deposits ORDER BY created_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
            out = []
            for r in rows:
                out.append({
                    "id": r["deposit_id"],
                    "from": r["from_addr"],
                    "amount": r["amount"],
                    "main_tx_hash": r["main_tx_hash"],
                    "created_at": r["created_at"],
                    "status": r["status"],
                })
            return out

    def save_plasma_block(self, block: Dict) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO plasma_blocks
                   (block_id, block_hash, parent_hash, transactions,
                    total_amount, tx_count, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    int(block["block_id"]),
                    block["block_hash"],
                    block["parent_hash"],
                    json.dumps(block.get("transactions", [])),
                    float(block.get("total_amount", 0)),
                    int(block.get("transaction_count", block.get("tx_count", 0))),
                    int(block.get("created_at", 0)),
                ),
            )
            self.conn.commit()

    def get_plasma_blocks(self, limit: int = 20) -> List[Dict]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM plasma_blocks ORDER BY block_id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
            out = []
            for r in rows:
                try:
                    txs = json.loads(r["transactions"] or "[]")
                except Exception:
                    txs = []
                out.append({
                    "block_id": r["block_id"],
                    "block_hash": r["block_hash"],
                    "parent_hash": r["parent_hash"],
                    "transactions": txs,
                    "total_amount": r["total_amount"],
                    "transaction_count": r["tx_count"],
                    "created_at": r["created_at"],
                })
            return sorted(out, key=lambda b: b["block_id"])

    def save_plasma_exit(self, ex: Dict) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO plasma_exits
                   (exit_id, deposit_id, user_addr, amount, created_at, status)
                   VALUES (?,?,?,?,?,?)""",
                (
                    ex["id"],
                    ex["deposit_id"],
                    ex["user"],
                    float(ex["amount"]),
                    int(ex.get("created_at", 0)),
                    ex.get("status", "pending"),
                ),
            )
            self.conn.commit()

    def get_plasma_exits(self, limit: int = 100) -> List[Dict]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM plasma_exits ORDER BY created_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
            out = []
            for r in rows:
                out.append({
                    "id": r["exit_id"],
                    "deposit_id": r["deposit_id"],
                    "user": r["user_addr"],
                    "amount": r["amount"],
                    "created_at": r["created_at"],
                    "status": r["status"],
                })
            return out

    # ── Crypto Will (Wave 41 persistence) ───────────────────────────────────

    def save_crypto_will(self, will: Dict) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO crypto_wills
                   (will_id, owner, heir, amount, assets, execution_time,
                    created_at, status, witnesses)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    will["will_id"],
                    will["owner"],
                    will["heir"],
                    float(will["amount"]),
                    json.dumps(will.get("assets", {})),
                    int(will.get("execution_time", 0)),
                    int(will.get("created_at", 0)),
                    will.get("status", "pending"),
                    json.dumps(will.get("witnesses", [])),
                ),
            )
            self.conn.commit()

    def get_crypto_wills(self, owner: str = "", status: str = "", limit: int = 100) -> List[Dict]:
        with self.lock:
            q = "SELECT * FROM crypto_wills WHERE 1=1"
            params: list = []
            if owner:
                q += " AND (owner=? OR heir=?)"
                params.extend([owner, owner])
            if status:
                q += " AND status=?"
                params.append(status)
            q += " ORDER BY created_at DESC LIMIT ?"
            params.append(int(limit))
            rows = self.conn.execute(q, params).fetchall()
            out = []
            for r in rows:
                try:
                    assets = json.loads(r["assets"] or "{}")
                except Exception:
                    assets = {}
                try:
                    witnesses = json.loads(r["witnesses"] or "[]")
                except Exception:
                    witnesses = []
                out.append({
                    "will_id": r["will_id"],
                    "owner": r["owner"],
                    "heir": r["heir"],
                    "amount": r["amount"],
                    "assets": assets,
                    "execution_time": r["execution_time"],
                    "created_at": r["created_at"],
                    "status": r["status"],
                    "witnesses": witnesses,
                })
            return out

    def delete_crypto_will(self, will_id: str) -> None:
        with self.lock:
            self.conn.execute("DELETE FROM crypto_wills WHERE will_id=?", (will_id,))
            self.conn.commit()

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
