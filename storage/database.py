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
            ("plasma_blocks", "merkle_root", "TEXT NOT NULL DEFAULT ''"),
            ("plasma_blocks", "tx_root",     "TEXT NOT NULL DEFAULT ''"),
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

        self._backfill_tx_receipts_v48()
        self._backfill_proposer_audit_v49()

    def _backfill_proposer_audit_v49(self) -> None:
        """Build proposer audit rows from historical blocks (Wave 49, idempotent)."""
        try:
            missing = self.conn.execute(
                """SELECT height, hash, miner, tx_count, total_burned, timestamp
                   FROM blocks
                   WHERE height NOT IN (SELECT height FROM block_proposer_audit)"""
            ).fetchall()
            for r in missing:
                self._insert_proposer_audit({
                    "height": r["height"],
                    "hash": r["hash"],
                    "miner": r["miner"],
                    "tx_count": r["tx_count"],
                    "total_burned": r["total_burned"],
                    "timestamp": r["timestamp"],
                })
            if missing:
                print(f"[DB] Wave 49: backfilled {len(missing)} proposer audit row(s)")
        except Exception as e:
            print(f"[DB] proposer audit backfill warning: {e}")

    def _backfill_tx_receipts_v48(self) -> None:
        """Build tx_receipts for transactions missing receipts (Wave 48, idempotent)."""
        try:
            missing = self.conn.execute(
                """SELECT t.*, b.hash AS block_hash
                   FROM transactions t
                   LEFT JOIN blocks b ON b.height = t.block_height
                   WHERE t.hash NOT IN (SELECT tx_hash FROM tx_receipts)"""
            ).fetchall()
            for r in missing:
                d = dict(r)
                self._insert_tx_receipt(
                    d,
                    d.get("block_hash") or "",
                    int(d.get("block_height") or 0),
                )
            if missing:
                print(f"[DB] Wave 48: backfilled {len(missing)} tx receipt(s)")
        except Exception as e:
            print(f"[DB] tx_receipts backfill warning: {e}")

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
            CREATE INDEX IF NOT EXISTS idx_evm_logs_block ON evm_logs(block_height);
            CREATE INDEX IF NOT EXISTS idx_evm_logs_tx ON evm_logs(tx_hash);

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

            CREATE TABLE IF NOT EXISTS oracle_reports (
                report_id   TEXT PRIMARY KEY,
                symbol      TEXT NOT NULL,
                reporter    TEXT NOT NULL,
                value       REAL NOT NULL,
                signature   TEXT NOT NULL DEFAULT '',
                payload     TEXT NOT NULL DEFAULT '{}',
                submitted_at INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_oracle_reports_symbol ON oracle_reports(symbol);

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

            CREATE TABLE IF NOT EXISTS lightning_htlcs (
                htlc_id       TEXT PRIMARY KEY,
                channel_id    TEXT NOT NULL,
                payment_hash  TEXT NOT NULL,
                amount        REAL NOT NULL,
                expiry        INTEGER NOT NULL,
                sender        TEXT NOT NULL,
                receiver      TEXT NOT NULL,
                status        TEXT NOT NULL DEFAULT 'pending',
                preimage      TEXT NOT NULL DEFAULT '',
                created_at    INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_ln_htlcs_channel ON lightning_htlcs(channel_id);

            CREATE TABLE IF NOT EXISTS lightning_channel_states (
                channel_id    TEXT NOT NULL,
                version       INTEGER NOT NULL,
                balance1      REAL NOT NULL,
                balance2      REAL NOT NULL,
                state_hash    TEXT NOT NULL,
                sig_node1     TEXT NOT NULL DEFAULT '',
                sig_node2     TEXT NOT NULL DEFAULT '',
                updated_at    INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (channel_id, version)
            );

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

            CREATE TABLE IF NOT EXISTS wasm_contracts (
                address     TEXT PRIMARY KEY,
                code        TEXT NOT NULL,
                owner       TEXT NOT NULL,
                name        TEXT NOT NULL DEFAULT '',
                created_at  INTEGER NOT NULL DEFAULT 0,
                call_count  INTEGER NOT NULL DEFAULT 0,
                storage_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS wasm_events (
                event_id      TEXT PRIMARY KEY,
                contract_addr TEXT NOT NULL DEFAULT '',
                event_type    TEXT NOT NULL DEFAULT '',
                payload       TEXT NOT NULL DEFAULT '{}',
                timestamp     INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_wasm_events_ts ON wasm_events(timestamp);

            CREATE TABLE IF NOT EXISTS ai_agents (
                agent_id          TEXT PRIMARY KEY,
                name              TEXT NOT NULL,
                owner             TEXT NOT NULL,
                agent_type        TEXT NOT NULL DEFAULT 'transformer',
                status            TEXT NOT NULL DEFAULT 'active',
                created_at        INTEGER NOT NULL DEFAULT 0,
                last_action       INTEGER NOT NULL DEFAULT 0,
                performance_score REAL NOT NULL DEFAULT 0,
                total_profit      REAL NOT NULL DEFAULT 0,
                actions_count     INTEGER NOT NULL DEFAULT 0,
                strategy_json     TEXT NOT NULL DEFAULT '{}',
                memory_json       TEXT NOT NULL DEFAULT '[]'
            );
            CREATE INDEX IF NOT EXISTS idx_ai_agents_owner ON ai_agents(owner);

            CREATE TABLE IF NOT EXISTS mev_simulations (
                sim_id     TEXT PRIMARY KEY,
                sim_type   TEXT NOT NULL,
                profit     REAL NOT NULL DEFAULT 0,
                payload    TEXT NOT NULL DEFAULT '{}',
                created_at INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_mev_sim_ts ON mev_simulations(created_at);

            CREATE TABLE IF NOT EXISTS reorg_assessments (
                assess_id  TEXT PRIMARY KEY,
                kind       TEXT NOT NULL,
                payload    TEXT NOT NULL DEFAULT '{}',
                created_at INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_reorg_assess_ts ON reorg_assessments(created_at);

            CREATE TABLE IF NOT EXISTS nft_tokens (
                token_id    TEXT PRIMARY KEY,
                name        TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                image_url   TEXT NOT NULL DEFAULT '',
                owner       TEXT NOT NULL DEFAULT '',
                creator     TEXT NOT NULL DEFAULT '',
                price       REAL NOT NULL DEFAULT 0,
                for_sale    INTEGER NOT NULL DEFAULT 0,
                created_at  INTEGER NOT NULL DEFAULT 0,
                metadata    TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_nft_owner ON nft_tokens(owner);

            CREATE TABLE IF NOT EXISTS nft_offers (
                offer_id    TEXT PRIMARY KEY,
                token_id    TEXT NOT NULL,
                bidder      TEXT NOT NULL DEFAULT '',
                price       REAL NOT NULL DEFAULT 0,
                expires_at  INTEGER NOT NULL DEFAULT 0,
                status      TEXT NOT NULL DEFAULT 'pending',
                created_at  INTEGER NOT NULL DEFAULT 0,
                payload     TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_nft_offer_token ON nft_offers(token_id);

            CREATE TABLE IF NOT EXISTS nft_auctions (
                auction_id  TEXT PRIMARY KEY,
                token_id    TEXT NOT NULL,
                seller      TEXT NOT NULL DEFAULT '',
                status      TEXT NOT NULL DEFAULT 'active',
                ends_at     INTEGER NOT NULL DEFAULT 0,
                payload     TEXT NOT NULL DEFAULT '{}',
                created_at  INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS nft_sales (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                token_id    TEXT NOT NULL,
                from_addr   TEXT NOT NULL DEFAULT '',
                to_addr     TEXT NOT NULL DEFAULT '',
                price       REAL NOT NULL DEFAULT 0,
                sale_type   TEXT NOT NULL DEFAULT 'buy',
                created_at  INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_nft_sales_ts ON nft_sales(created_at);

            CREATE TABLE IF NOT EXISTS tx_receipts (
                tx_hash       TEXT PRIMARY KEY,
                block_height  INTEGER NOT NULL,
                block_hash    TEXT NOT NULL DEFAULT '',
                from_addr     TEXT NOT NULL DEFAULT '',
                to_addr       TEXT NOT NULL DEFAULT '',
                value         REAL NOT NULL DEFAULT 0,
                fee           REAL NOT NULL DEFAULT 0,
                burned        REAL NOT NULL DEFAULT 0,
                gas_used      INTEGER NOT NULL DEFAULT 0,
                status        INTEGER NOT NULL DEFAULT 1,
                created_at    INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_tx_receipt_block ON tx_receipts(block_height);

            CREATE TABLE IF NOT EXISTS block_proposer_audit (
                height        INTEGER PRIMARY KEY,
                block_hash    TEXT NOT NULL DEFAULT '',
                proposer      TEXT NOT NULL DEFAULT '',
                tx_count      INTEGER NOT NULL DEFAULT 0,
                total_burned  REAL NOT NULL DEFAULT 0.0,
                block_ts      INTEGER NOT NULL DEFAULT 0,
                recorded_at   INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_proposer_audit_addr ON block_proposer_audit(proposer);
            CREATE INDEX IF NOT EXISTS idx_proposer_audit_ts ON block_proposer_audit(block_ts);

            CREATE TABLE IF NOT EXISTS state_root_mismatches (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                height        INTEGER NOT NULL,
                expected_root TEXT NOT NULL DEFAULT '',
                computed_root TEXT NOT NULL DEFAULT '',
                source        TEXT NOT NULL DEFAULT 'p2p',
                proposer      TEXT NOT NULL DEFAULT '',
                created_at    INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_state_root_mm_height ON state_root_mismatches(height);

            CREATE TABLE IF NOT EXISTS tx_propagation_events (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_hash       TEXT NOT NULL,
                stage         TEXT NOT NULL,
                node_id       TEXT NOT NULL DEFAULT '',
                peer_id       TEXT NOT NULL DEFAULT '',
                block_height  INTEGER NOT NULL DEFAULT 0,
                detail        TEXT NOT NULL DEFAULT '{}',
                created_at    INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_tx_prop_stage ON tx_propagation_events(tx_hash);
            CREATE INDEX IF NOT EXISTS idx_tx_prop_ts ON tx_propagation_events(created_at);

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
        self._insert_proposer_audit(block)

    def _insert_proposer_audit(self, block: Dict) -> None:
        height = int(block.get("height", block.get("number", 0)) or 0)
        block_hash = block.get("hash", block.get("block_hash", "")) or ""
        proposer = self._normalize_address(
            block.get("miner", block.get("proposer", "genesis")) or "genesis"
        )
        self.conn.execute(
            """INSERT OR REPLACE INTO block_proposer_audit
               (height, block_hash, proposer, tx_count, total_burned, block_ts, recorded_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                height,
                block_hash,
                proposer,
                int(block.get("tx_count", len(block.get("transactions", []))) or 0),
                float(block.get("total_burned", 0.0) or 0.0),
                int(block.get("timestamp", int(time.time())) or 0),
                int(time.time()),
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
        block_hash = block.get("hash", block.get("block_hash", ""))
        block_height = int(block.get("height", block.get("number", 0)) or 0)
        for tx in transactions:
            self._insert_transaction(tx)
            self._insert_tx_receipt(tx, block_hash, block_height)
            tx_hash = tx.get("hash", tx.get("tx_hash", ""))
            if tx_hash:
                proposer = self._normalize_address(
                    block.get("miner", block.get("proposer", ""))
                )
                self.record_tx_propagation_event(
                    tx_hash,
                    "block_included",
                    block_height=block_height,
                    detail={"proposer": proposer, "block_hash": block_hash},
                    _no_commit=True,
                )
                self.record_tx_propagation_event(
                    tx_hash,
                    "block_confirmed",
                    block_height=block_height,
                    detail={"receipt": True},
                    _no_commit=True,
                )
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

    def compute_state_root(self) -> str:
        from execution.state_root import compute_db_state_root

        return compute_db_state_root(self.get_all_accounts())

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

    def reorg_truncate_above(self, height: int) -> None:
        """Remove chain rows above height. Caller must hold atomic()."""
        cut = int(height)
        self.conn.execute(
            "DELETE FROM transactions WHERE block_height > ?", (cut,)
        )
        self.conn.execute(
            "DELETE FROM tx_receipts WHERE block_height > ?", (cut,)
        )
        self.conn.execute(
            "DELETE FROM block_proposer_audit WHERE height > ?", (cut,)
        )
        self.conn.execute(
            "DELETE FROM state_root_mismatches WHERE height > ?", (cut,)
        )
        self.conn.execute(
            "DELETE FROM burn_stats WHERE block_height > ?", (cut,)
        )
        self.conn.execute("DELETE FROM blocks WHERE height > ?", (cut,))

    def truncate_chain_state(self, height: int) -> int:
        """Remove blocks, txs, and burn stats above height."""
        with self.atomic():
            before = self.get_chain_tip()
            self.reorg_truncate_above(int(height))
            return max(0, before - int(height))

    def reset_accounts_from_alloc(
        self, alloc: Dict[str, float], *, _in_atomic: bool = False
    ) -> None:
        """Reset all account balances/nonces from genesis allocation map."""
        if _in_atomic:
            self._reset_accounts_from_alloc_locked(alloc)
            return
        with self.atomic():
            self._reset_accounts_from_alloc_locked(alloc)

    def _reset_accounts_from_alloc_locked(self, alloc: Dict[str, float]) -> None:
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

    @staticmethod
    def _normalize_tx_status(status: Any) -> int:
        if status is None:
            return 1
        if isinstance(status, bool):
            return 1 if status else 0
        if isinstance(status, (int, float)):
            return 1 if int(status) != 0 else 0
        s = str(status).strip().lower()
        if s in ("1", "true", "ok", "success", "confirmed", "mined"):
            return 1
        if s in ("0", "false", "failed", "reverted", "pending"):
            return 0
        try:
            return 1 if int(s) != 0 else 0
        except ValueError:
            return 1

    def _insert_transaction(self, tx: Dict) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO transactions
               (hash, block_height, from_addr, to_addr, value,
                gas, gas_used, fee, burned, nonce, tx_data, status, timestamp)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                tx.get("hash", tx.get("tx_hash", "")),
                tx.get("block_height", 0),
                self._normalize_address(tx.get("from_addr", tx.get("from", ""))),
                self._normalize_address(tx.get("to_addr", tx.get("to", ""))),
                tx.get("value", tx.get("amount", 0.0)),
                tx.get("gas", 21000),
                tx.get("gas_used", tx.get("gas", 21000)),
                tx.get("fee", 0.0),
                tx.get("burned", 0.0),
                tx.get("nonce", 0),
                tx.get("data", tx.get("tx_data", "")),
                self._normalize_tx_status(tx.get("status", 1)),
                tx.get("timestamp", int(time.time())),
            ),
        )

    def _insert_tx_receipt(self, tx: Dict, block_hash: str, block_height: int) -> None:
        tx_hash = tx.get("hash", tx.get("tx_hash", ""))
        if not tx_hash:
            return
        self.conn.execute(
            """INSERT OR REPLACE INTO tx_receipts
               (tx_hash, block_height, block_hash, from_addr, to_addr, value,
                fee, burned, gas_used, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                tx_hash,
                int(tx.get("block_height", block_height) or block_height),
                block_hash,
                self._normalize_address(tx.get("from_addr", tx.get("from", ""))),
                self._normalize_address(tx.get("to_addr", tx.get("to", ""))),
                float(tx.get("value", tx.get("amount", 0.0))),
                float(tx.get("fee", 0.0)),
                float(tx.get("burned", 0.0)),
                int(tx.get("gas_used", tx.get("gas", 21000))),
                self._normalize_tx_status(tx.get("status", 1)),
                int(tx.get("timestamp", time.time())),
            ),
        )

    def get_tx_receipt(self, tx_hash: str) -> Optional[Dict]:
        with self.lock:
            row = self.conn.execute(
                "SELECT * FROM tx_receipts WHERE tx_hash = ?", (tx_hash,)
            ).fetchone()
            if not row:
                return None
            return {
                "tx_hash": row["tx_hash"],
                "block_height": row["block_height"],
                "block_hash": row["block_hash"],
                "from": row["from_addr"],
                "to": row["to_addr"],
                "value": row["value"],
                "fee": row["fee"],
                "burned": row["burned"],
                "gas_used": row["gas_used"],
                "status": row["status"],
                "timestamp": row["created_at"],
            }

    def get_receipts_by_block(self, block_height: int) -> List[Dict]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM tx_receipts WHERE block_height = ? ORDER BY created_at",
                (int(block_height),),
            ).fetchall()
            return [
                {
                    "tx_hash": r["tx_hash"],
                    "block_height": r["block_height"],
                    "block_hash": r["block_hash"],
                    "from": r["from_addr"],
                    "to": r["to_addr"],
                    "value": r["value"],
                    "fee": r["fee"],
                    "burned": r["burned"],
                    "gas_used": r["gas_used"],
                    "status": r["status"],
                    "timestamp": r["created_at"],
                }
                for r in rows
            ]

    def get_chain_metrics(self, window: int = 32) -> Dict:
        """Core L1 metrics: block time, throughput hints."""
        with self.lock:
            tip = self.get_chain_tip()
            tx_count = self.conn.execute(
                "SELECT COUNT(*) as c FROM transactions"
            ).fetchone()["c"]
            receipt_count = 0
            proposer_audit_count = 0
            try:
                receipt_count = self.conn.execute(
                    "SELECT COUNT(*) as c FROM tx_receipts"
                ).fetchone()["c"]
                proposer_audit_count = self.conn.execute(
                    "SELECT COUNT(*) as c FROM block_proposer_audit"
                ).fetchone()["c"]
            except Exception:
                pass
            rows = self.conn.execute(
                "SELECT height, timestamp, tx_count, total_burned FROM blocks "
                "ORDER BY height DESC LIMIT ?",
                (int(window),),
            ).fetchall()
            avg_block_time = 0.0
            if len(rows) >= 2:
                intervals = []
                ordered = sorted(rows, key=lambda r: r["height"])
                for i in range(1, len(ordered)):
                    dt = int(ordered[i]["timestamp"]) - int(ordered[i - 1]["timestamp"])
                    if dt > 0:
                        intervals.append(dt)
                if intervals:
                    avg_block_time = sum(intervals) / len(intervals)
            target = 15.0
            return {
                "height": tip,
                "tx_count": int(tx_count),
                "receipt_count": int(receipt_count),
                "proposer_audit_count": int(proposer_audit_count),
                "receipts_enabled": True,
                "proposer_audit_enabled": True,
                "state_root_strict_p2p": True,
                "avg_block_time_sec": round(avg_block_time, 2),
                "target_block_time_sec": target,
                "blocks_sampled": len(rows),
                "burn_last_window": round(
                    sum(float(r["total_burned"] or 0) for r in rows), 6
                ),
            }

    def get_proposer_audit_log(
        self,
        limit: int = 50,
        offset: int = 0,
        proposer: str = "",
    ) -> List[Dict]:
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))
        with self.lock:
            if proposer:
                addr = self._normalize_address(proposer)
                rows = self.conn.execute(
                    """SELECT * FROM block_proposer_audit
                       WHERE proposer=?
                       ORDER BY height DESC LIMIT ? OFFSET ?""",
                    (addr, limit, offset),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    """SELECT * FROM block_proposer_audit
                       ORDER BY height DESC LIMIT ? OFFSET ?""",
                    (limit, offset),
                ).fetchall()
            return [
                {
                    "height": r["height"],
                    "block_hash": r["block_hash"],
                    "proposer": r["proposer"],
                    "tx_count": r["tx_count"],
                    "total_burned": r["total_burned"],
                    "timestamp": r["block_ts"],
                    "recorded_at": r["recorded_at"],
                }
                for r in rows
            ]

    def count_proposer_audit(
        self, proposer: str = ""
    ) -> int:
        with self.lock:
            if proposer:
                addr = self._normalize_address(proposer)
                return int(self.conn.execute(
                    "SELECT COUNT(*) as c FROM block_proposer_audit WHERE proposer=?",
                    (addr,),
                ).fetchone()["c"])
            return int(self.conn.execute(
                "SELECT COUNT(*) as c FROM block_proposer_audit"
            ).fetchone()["c"])

    def get_proposer_stats(self, limit: int = 20) -> List[Dict]:
        """Top proposers by blocks proposed."""
        limit = max(1, min(int(limit), 100))
        with self.lock:
            rows = self.conn.execute(
                """SELECT proposer,
                          COUNT(*) as blocks_proposed,
                          SUM(tx_count) as total_txs,
                          SUM(total_burned) as total_burned,
                          MAX(height) as last_height,
                          MIN(height) as first_height
                   FROM block_proposer_audit
                   GROUP BY proposer
                   ORDER BY blocks_proposed DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_proposer_detail(self, address: str, recent_limit: int = 10) -> Dict:
        addr = self._normalize_address(address)
        with self.lock:
            row = self.conn.execute(
                """SELECT COUNT(*) as blocks_proposed,
                          SUM(tx_count) as total_txs,
                          SUM(total_burned) as total_burned,
                          MAX(height) as last_height,
                          MIN(height) as first_height
                   FROM block_proposer_audit WHERE proposer=?""",
                (addr,),
            ).fetchone()
            recent = self.get_proposer_audit_log(
                limit=recent_limit, offset=0, proposer=addr
            )
            return {
                "proposer": addr,
                "blocks_proposed": int(row["blocks_proposed"] or 0),
                "total_txs": int(row["total_txs"] or 0),
                "total_burned": float(row["total_burned"] or 0.0),
                "first_height": row["first_height"],
                "last_height": row["last_height"],
                "recent_blocks": recent,
            }

    def record_state_root_mismatch(
        self,
        height: int,
        expected_root: str,
        computed_root: str,
        source: str = "p2p",
        proposer: str = "",
    ) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT INTO state_root_mismatches
                   (height, expected_root, computed_root, source, proposer, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (
                    int(height),
                    str(expected_root or ""),
                    str(computed_root or ""),
                    str(source or "p2p"),
                    self._normalize_address(proposer),
                    int(time.time()),
                ),
            )
            self.conn.commit()

    def get_state_root_mismatches(self, limit: int = 20) -> List[Dict]:
        limit = max(1, min(int(limit), 100))
        with self.lock:
            rows = self.conn.execute(
                """SELECT height, expected_root, computed_root, source, proposer, created_at
                   FROM state_root_mismatches
                   ORDER BY id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def record_tx_propagation_event(
        self,
        tx_hash: str,
        stage: str,
        node_id: str = "",
        peer_id: str = "",
        block_height: int = 0,
        detail: Any = None,
        _no_commit: bool = False,
    ) -> None:
        if not tx_hash or not stage:
            return
        payload = detail if isinstance(detail, dict) else {}
        with self.lock:
            self.conn.execute(
                """INSERT INTO tx_propagation_events
                   (tx_hash, stage, node_id, peer_id, block_height, detail, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    str(tx_hash),
                    str(stage),
                    str(node_id or ""),
                    str(peer_id or ""),
                    int(block_height or 0),
                    json.dumps(payload, ensure_ascii=False),
                    int(time.time()),
                ),
            )
            if not _no_commit:
                self.conn.commit()

    def get_tx_propagation_trace(self, tx_hash: str) -> Dict:
        with self.lock:
            rows = self.conn.execute(
                """SELECT stage, node_id, peer_id, block_height, detail, created_at
                   FROM tx_propagation_events
                   WHERE tx_hash=?
                   ORDER BY id ASC""",
                (str(tx_hash),),
            ).fetchall()
            events = []
            for r in rows:
                try:
                    detail = json.loads(r["detail"] or "{}")
                except Exception:
                    detail = {}
                events.append({
                    "stage": r["stage"],
                    "node_id": r["node_id"],
                    "peer_id": r["peer_id"],
                    "block_height": r["block_height"],
                    "detail": detail,
                    "timestamp": r["created_at"],
                })
            receipt = self.get_tx_receipt(tx_hash)
            tx_row = self.get_transaction(tx_hash)
            stages = [e["stage"] for e in events]
            status = "unknown"
            if receipt or tx_row:
                status = "confirmed"
            elif "block_included" in stages:
                status = "included"
            elif "mempool_local" in stages or "mempool_remote" in stages:
                status = "mempool"
            elif events:
                status = "propagating"
            return {
                "tx_hash": tx_hash,
                "status": status,
                "events": events,
                "receipt": receipt,
                "transaction": tx_row,
            }

    def get_recent_tx_propagation(self, limit: int = 20) -> List[Dict]:
        limit = max(1, min(int(limit), 100))
        with self.lock:
            rows = self.conn.execute(
                """SELECT tx_hash, MAX(created_at) as last_ts
                   FROM tx_propagation_events
                   GROUP BY tx_hash
                   ORDER BY last_ts DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
            return [
                self.get_tx_propagation_trace(r["tx_hash"])
                for r in rows
            ]

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

    @staticmethod
    def _normalize_address(address: str) -> str:
        return (address or "").strip().lower()

    def _serialize_tx_row(self, row: Dict, viewer_addr: str = "") -> Dict:
        viewer = self._normalize_address(viewer_addr)
        from_addr = self._normalize_address(row.get("from_addr", ""))
        to_addr = self._normalize_address(row.get("to_addr", ""))
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
            "status": self._normalize_tx_status(row.get("status", 1)),
            "timestamp": int(row.get("timestamp", 0)),
            "direction": direction,
        }

    def count_address_transactions(
        self, address: str, direction: str = "all"
    ) -> int:
        addr = self._normalize_address(address)
        if not addr:
            return 0
        with self.lock:
            if direction == "sent":
                q = "SELECT COUNT(*) as c FROM transactions WHERE LOWER(from_addr)=?"
                params: tuple = (addr,)
            elif direction == "received":
                q = "SELECT COUNT(*) as c FROM transactions WHERE LOWER(to_addr)=?"
                params = (addr,)
            else:
                q = (
                    "SELECT COUNT(*) as c FROM transactions "
                    "WHERE LOWER(from_addr)=? OR LOWER(to_addr)=?"
                )
                params = (addr, addr)
            return int(self.conn.execute(q, params).fetchone()["c"])

    def get_transactions_by_address(
        self,
        address: str,
        limit: int = 50,
        offset: int = 0,
        direction: str = "all",
    ) -> List[Dict]:
        addr = self._normalize_address(address)
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))
        with self.lock:
            if direction == "sent":
                where = "LOWER(from_addr)=?"
                params: List = [addr]
            elif direction == "received":
                where = "LOWER(to_addr)=?"
                params = [addr]
            else:
                where = "(LOWER(from_addr)=? OR LOWER(to_addr)=?)"
                params = [addr, addr]
            rows = self.conn.execute(
                f"""SELECT * FROM transactions
                    WHERE {where}
                    ORDER BY block_height DESC, rowid DESC
                    LIMIT ? OFFSET ?""",
                (*params, limit, offset),
            ).fetchall()
            return [self._serialize_tx_row(dict(r), addr) for r in rows]

    def get_address_activity(self, address: str) -> Dict:
        addr = self._normalize_address(address)
        with self.lock:
            sent = int(self.conn.execute(
                "SELECT COUNT(*) as c FROM transactions WHERE LOWER(from_addr)=?",
                (addr,),
            ).fetchone()["c"])
            received = int(self.conn.execute(
                "SELECT COUNT(*) as c FROM transactions WHERE LOWER(to_addr)=?",
                (addr,),
            ).fetchone()["c"])
            total = int(self.conn.execute(
                "SELECT COUNT(*) as c FROM transactions "
                "WHERE LOWER(from_addr)=? OR LOWER(to_addr)=?",
                (addr, addr),
            ).fetchone()["c"])
            blocks_proposed = int(self.conn.execute(
                "SELECT COUNT(*) as c FROM blocks WHERE LOWER(miner)=?",
                (addr,),
            ).fetchone()["c"])
            row = self.conn.execute(
                """SELECT MAX(block_height) as h FROM transactions
                   WHERE LOWER(from_addr)=? OR LOWER(to_addr)=?""",
                (addr, addr),
            ).fetchone()
            last_h = int(row["h"]) if row and row["h"] is not None else None
            bal_row = self.conn.execute(
                "SELECT balance FROM accounts WHERE address=?", (addr,)
            ).fetchone()
            nonce_row = self.conn.execute(
                "SELECT nonce FROM accounts WHERE address=?", (addr,)
            ).fetchone()
            code_row = self.conn.execute(
                "SELECT code FROM accounts WHERE address=?", (addr,)
            ).fetchone()
            return {
                "address": addr,
                "balance": float(bal_row["balance"]) if bal_row else 0.0,
                "nonce": int(nonce_row["nonce"]) if nonce_row else 0,
                "sent_count": sent,
                "received_count": received,
                "tx_count": total,
                "blocks_proposed": blocks_proposed,
                "last_tx_height": last_h,
                "is_contract": bool(code_row and code_row["code"]),
            }

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
        return self.query_evm_logs(
            addresses=[contract_address] if contract_address else None,
            limit=limit,
        )

    def get_evm_logs_by_tx(self, tx_hash: str) -> List[Dict]:
        if not tx_hash:
            return []
        with self.lock:
            rows = self.conn.execute(
                """SELECT * FROM evm_logs WHERE tx_hash=?
                   ORDER BY log_index ASC, id ASC""",
                (tx_hash,),
            ).fetchall()
            return self._rows_to_evm_logs(rows)

    def query_evm_logs(
        self,
        from_block: int = 0,
        to_block: Optional[int] = None,
        addresses: Optional[List[str]] = None,
        topics: Optional[List] = None,
        limit: int = 10_000,
    ) -> List[Dict]:
        """Query persisted EVM logs (eth_getLogs-style filter)."""
        to_block = 2**63 - 1 if to_block is None else int(to_block)
        from_block = max(0, int(from_block))
        clauses = ["block_height >= ?", "block_height <= ?"]
        params: List = [from_block, to_block]
        if addresses:
            normalized = [self._normalize_address(a) for a in addresses if a]
            if normalized:
                placeholders = ",".join("?" for _ in normalized)
                clauses.append(f"contract_address IN ({placeholders})")
                params.extend(normalized)
        sql = (
            "SELECT * FROM evm_logs WHERE "
            + " AND ".join(clauses)
            + " ORDER BY block_height ASC, log_index ASC, id ASC LIMIT ?"
        )
        params.append(int(limit))
        with self.lock:
            rows = self.conn.execute(sql, params).fetchall()
        logs = self._rows_to_evm_logs(rows)
        if topics:
            logs = [row for row in logs if self._evm_log_topics_match(row.get("topics", []), topics)]
        return logs

    @staticmethod
    def _rows_to_evm_logs(rows) -> List[Dict]:
        out = []
        for r in rows:
            item = dict(r)
            try:
                item["topics"] = json.loads(item.get("topics") or "[]")
            except Exception:
                item["topics"] = []
            out.append(item)
        return out

    @staticmethod
    def _evm_log_topics_match(log_topics: List, filter_topics: List) -> bool:
        if not filter_topics:
            return True
        for i, rule in enumerate(filter_topics):
            if rule is None:
                continue
            if i >= len(log_topics):
                return False
            log_topic = str(log_topics[i]).lower()
            if isinstance(rule, (list, tuple)):
                allowed = {str(t).lower() for t in rule if t is not None}
                if log_topic not in allowed:
                    return False
            elif log_topic != str(rule).lower():
                return False
        return True

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

    def save_oracle_report(self, report: Dict) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO oracle_reports
                   (report_id, symbol, reporter, value, signature, payload, submitted_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    report["report_id"],
                    report["symbol"],
                    report["reporter"],
                    float(report["value"]),
                    report.get("signature", ""),
                    report.get("payload", "{}"),
                    int(report.get("submitted_at", 0)),
                ),
            )
            self.conn.commit()

    def get_oracle_reports(
        self, symbol: str = "", since: int = 0, limit: int = 50
    ) -> List[Dict]:
        with self.lock:
            if symbol:
                rows = self.conn.execute(
                    """SELECT * FROM oracle_reports
                       WHERE symbol=? AND submitted_at>=?
                       ORDER BY submitted_at DESC LIMIT ?""",
                    (symbol.lower(), int(since), int(limit)),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    """SELECT * FROM oracle_reports
                       WHERE submitted_at>=?
                       ORDER BY submitted_at DESC LIMIT ?""",
                    (int(since), int(limit)),
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

    def save_lightning_htlc(self, h: Dict) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO lightning_htlcs
                   (htlc_id, channel_id, payment_hash, amount, expiry,
                    sender, receiver, status, preimage, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    h["htlc_id"],
                    h["channel_id"],
                    h["payment_hash"],
                    float(h["amount"]),
                    int(h["expiry"]),
                    h["sender"],
                    h["receiver"],
                    h.get("status", "pending"),
                    h.get("preimage", ""),
                    int(h.get("created_at", 0)),
                ),
            )
            self.conn.commit()

    def get_lightning_htlcs(self, channel_id: str = "", limit: int = 100) -> List[Dict]:
        with self.lock:
            if channel_id:
                rows = self.conn.execute(
                    "SELECT * FROM lightning_htlcs WHERE channel_id=? ORDER BY created_at DESC LIMIT ?",
                    (channel_id, int(limit)),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    "SELECT * FROM lightning_htlcs ORDER BY created_at DESC LIMIT ?",
                    (int(limit),),
                ).fetchall()
            return [dict(r) for r in rows]

    def save_lightning_channel_state(self, st: Dict) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO lightning_channel_states
                   (channel_id, version, balance1, balance2, state_hash,
                    sig_node1, sig_node2, updated_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    st["channel_id"],
                    int(st["version"]),
                    float(st["balance1"]),
                    float(st["balance2"]),
                    st["state_hash"],
                    st.get("sig_node1", ""),
                    st.get("sig_node2", ""),
                    int(st.get("updated_at", 0)),
                ),
            )
            self.conn.commit()

    def get_lightning_channel_state(self, channel_id: str) -> Optional[Dict]:
        with self.lock:
            row = self.conn.execute(
                """SELECT * FROM lightning_channel_states
                   WHERE channel_id=? ORDER BY version DESC LIMIT 1""",
                (channel_id,),
            ).fetchone()
            return dict(row) if row else None

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
                    total_amount, tx_count, created_at, merkle_root, tx_root)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    int(block["block_id"]),
                    block["block_hash"],
                    block["parent_hash"],
                    json.dumps(block.get("transactions", [])),
                    float(block.get("total_amount", 0)),
                    int(block.get("transaction_count", block.get("tx_count", 0))),
                    int(block.get("created_at", 0)),
                    block.get("merkle_root", ""),
                    block.get("tx_root", block.get("merkle_root", "")),
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

    # ── WASM VM (Wave 42 persistence) ─────────────────────────────────────────

    def save_wasm_contract(self, contract: Dict) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO wasm_contracts
                   (address, code, owner, name, created_at, call_count, storage_json)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    contract["address"],
                    contract.get("code", ""),
                    contract["owner"],
                    contract.get("name", ""),
                    int(contract.get("created_at", 0)),
                    int(contract.get("call_count", 0)),
                    json.dumps(contract.get("storage", {})),
                ),
            )
            self.conn.commit()

    def get_wasm_contracts(self, limit: int = 200) -> List[Dict]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM wasm_contracts ORDER BY created_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
            out = []
            for r in rows:
                try:
                    storage = json.loads(r["storage_json"] or "{}")
                except Exception:
                    storage = {}
                out.append({
                    "address": r["address"],
                    "code": r["code"],
                    "owner": r["owner"],
                    "name": r["name"],
                    "created_at": r["created_at"],
                    "call_count": r["call_count"],
                    "storage": storage,
                })
            return out

    def get_wasm_contract(self, address: str) -> Optional[Dict]:
        with self.lock:
            row = self.conn.execute(
                "SELECT * FROM wasm_contracts WHERE address=?", (address,)
            ).fetchone()
            if not row:
                return None
            try:
                storage = json.loads(row["storage_json"] or "{}")
            except Exception:
                storage = {}
            return {
                "address": row["address"],
                "code": row["code"],
                "owner": row["owner"],
                "name": row["name"],
                "created_at": row["created_at"],
                "call_count": row["call_count"],
                "storage": storage,
            }

    def save_wasm_event(self, event: Dict) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO wasm_events
                   (event_id, contract_addr, event_type, payload, timestamp)
                   VALUES (?,?,?,?,?)""",
                (
                    event["event_id"],
                    event.get("contract_addr", ""),
                    event.get("event_type", event.get("type", "")),
                    json.dumps(event.get("payload", event)),
                    int(event.get("timestamp", 0)),
                ),
            )
            self.conn.commit()

    def get_wasm_events(self, limit: int = 100) -> List[Dict]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM wasm_events ORDER BY timestamp DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
            out = []
            for r in rows:
                try:
                    payload = json.loads(r["payload"] or "{}")
                except Exception:
                    payload = {}
                out.append({
                    "event_id": r["event_id"],
                    "contract_addr": r["contract_addr"],
                    "event_type": r["event_type"],
                    "payload": payload,
                    "timestamp": r["timestamp"],
                })
            return out

    # ── AI Agents (Wave 43 persistence) ─────────────────────────────────────

    def save_ai_agent(self, agent: Dict) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO ai_agents
                   (agent_id, name, owner, agent_type, status, created_at,
                    last_action, performance_score, total_profit, actions_count,
                    strategy_json, memory_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    agent["agent_id"],
                    agent["name"],
                    agent["owner"],
                    agent.get("agent_type", "transformer"),
                    agent.get("status", "active"),
                    int(agent.get("created_at", 0)),
                    int(agent.get("last_action", 0)),
                    float(agent.get("performance_score", 0)),
                    float(agent.get("total_profit", 0)),
                    int(agent.get("actions_count", 0)),
                    json.dumps(agent.get("strategy", {})),
                    json.dumps(agent.get("memory", [])),
                ),
            )
            self.conn.commit()

    def get_ai_agents(self, owner: str = "", limit: int = 200) -> List[Dict]:
        with self.lock:
            if owner:
                rows = self.conn.execute(
                    "SELECT * FROM ai_agents WHERE owner=? ORDER BY created_at DESC LIMIT ?",
                    (owner, int(limit)),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    "SELECT * FROM ai_agents ORDER BY created_at DESC LIMIT ?",
                    (int(limit),),
                ).fetchall()
            out = []
            for r in rows:
                try:
                    strategy = json.loads(r["strategy_json"] or "{}")
                except Exception:
                    strategy = {}
                try:
                    memory = json.loads(r["memory_json"] or "[]")
                except Exception:
                    memory = []
                out.append({
                    "agent_id": r["agent_id"],
                    "name": r["name"],
                    "owner": r["owner"],
                    "agent_type": r["agent_type"],
                    "status": r["status"],
                    "created_at": r["created_at"],
                    "last_action": r["last_action"],
                    "performance_score": r["performance_score"],
                    "total_profit": r["total_profit"],
                    "actions_count": r["actions_count"],
                    "strategy": strategy,
                    "memory": memory,
                })
            return out

    def get_ai_agent(self, agent_id: str) -> Optional[Dict]:
        rows = self.get_ai_agents(limit=500)
        for r in rows:
            if r["agent_id"] == agent_id:
                return r
        return None

    # ── MEV simulations (Wave 44 persistence) ───────────────────────────────

    def save_mev_simulation(self, sim: Dict) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO mev_simulations
                   (sim_id, sim_type, profit, payload, created_at)
                   VALUES (?,?,?,?,?)""",
                (
                    sim["sim_id"],
                    sim.get("sim_type", sim.get("type", "")),
                    float(sim.get("profit", 0)),
                    json.dumps(sim.get("payload", sim)),
                    int(sim.get("created_at", 0)),
                ),
            )
            self.conn.commit()

    def get_mev_simulations(self, limit: int = 100) -> List[Dict]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM mev_simulations ORDER BY created_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
            out = []
            for r in rows:
                try:
                    payload = json.loads(r["payload"] or "{}")
                except Exception:
                    payload = {}
                out.append({
                    "sim_id": r["sim_id"],
                    "sim_type": r["sim_type"],
                    "profit": r["profit"],
                    "payload": payload,
                    "created_at": r["created_at"],
                })
            return out

    # ── Reorg assessments (Wave 45 persistence) ─────────────────────────────

    def save_reorg_assessment(self, assess: Dict) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO reorg_assessments
                   (assess_id, kind, payload, created_at)
                   VALUES (?,?,?,?)""",
                (
                    assess["assess_id"],
                    assess.get("kind", ""),
                    json.dumps({k: v for k, v in assess.items() if k != "assess_id"}),
                    int(assess.get("timestamp", assess.get("created_at", 0))),
                ),
            )
            self.conn.commit()

    def get_reorg_assessments(self, limit: int = 100) -> List[Dict]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM reorg_assessments ORDER BY created_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
            out = []
            for r in rows:
                try:
                    payload = json.loads(r["payload"] or "{}")
                except Exception:
                    payload = {}
                out.append({
                    "assess_id": r["assess_id"],
                    "kind": r["kind"],
                    "timestamp": r["created_at"],
                    **payload,
                })
            return out

    # ── NFT marketplace (Wave 46 persistence) ─────────────────────────────────

    def save_nft_token(self, token: Dict) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO nft_tokens
                   (token_id, name, description, image_url, owner, creator,
                    price, for_sale, created_at, metadata)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    token["token_id"],
                    token.get("name", ""),
                    token.get("description", ""),
                    token.get("image_url", ""),
                    token.get("owner", ""),
                    token.get("creator", ""),
                    float(token.get("price", 0)),
                    1 if token.get("for_sale") else 0,
                    int(token.get("created_at", 0)),
                    json.dumps(token.get("metadata") or {}),
                ),
            )
            self.conn.commit()

    def get_nft_tokens(self) -> List[Dict]:
        with self.lock:
            rows = self.conn.execute("SELECT * FROM nft_tokens ORDER BY created_at").fetchall()
            out = []
            for r in rows:
                try:
                    meta = json.loads(r["metadata"] or "{}")
                except Exception:
                    meta = {}
                out.append({
                    "token_id": r["token_id"],
                    "name": r["name"],
                    "description": r["description"],
                    "image_url": r["image_url"],
                    "owner": r["owner"],
                    "creator": r["creator"],
                    "price": r["price"],
                    "for_sale": bool(r["for_sale"]),
                    "created_at": r["created_at"],
                    "metadata": meta,
                })
            return out

    def save_nft_offer(self, offer: Dict) -> None:
        with self.lock:
            payload = {k: v for k, v in offer.items() if k != "offer_id"}
            self.conn.execute(
                """INSERT OR REPLACE INTO nft_offers
                   (offer_id, token_id, bidder, price, expires_at, status, created_at, payload)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    offer["offer_id"],
                    offer.get("token_id", ""),
                    offer.get("bidder", ""),
                    float(offer.get("price", 0)),
                    int(offer.get("expires_at", 0)),
                    offer.get("status", "pending"),
                    int(offer.get("created_at", 0)),
                    json.dumps(payload),
                ),
            )
            self.conn.commit()

    def get_nft_offers(self) -> List[Dict]:
        with self.lock:
            rows = self.conn.execute("SELECT * FROM nft_offers ORDER BY created_at DESC").fetchall()
            out = []
            for r in rows:
                try:
                    payload = json.loads(r["payload"] or "{}")
                except Exception:
                    payload = {}
                out.append({"offer_id": r["offer_id"], **payload})
            return out

    def save_nft_auction(self, auction: Dict) -> None:
        with self.lock:
            aid = auction["auction_id"]
            payload = {k: v for k, v in auction.items() if k != "auction_id"}
            self.conn.execute(
                """INSERT OR REPLACE INTO nft_auctions
                   (auction_id, token_id, seller, status, ends_at, payload, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    aid,
                    auction.get("token_id", ""),
                    auction.get("seller", ""),
                    auction.get("status", "active"),
                    int(auction.get("ends_at", 0)),
                    json.dumps(payload),
                    int(auction.get("created_at", 0)),
                ),
            )
            self.conn.commit()

    def get_nft_auctions(self) -> List[Dict]:
        with self.lock:
            rows = self.conn.execute("SELECT * FROM nft_auctions ORDER BY created_at DESC").fetchall()
            out = []
            for r in rows:
                try:
                    payload = json.loads(r["payload"] or "{}")
                except Exception:
                    payload = {}
                out.append({"auction_id": r["auction_id"], **payload})
            return out

    def save_nft_sale(self, sale: Dict) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT INTO nft_sales
                   (token_id, from_addr, to_addr, price, sale_type, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (
                    sale.get("token_id", ""),
                    sale.get("from", sale.get("from_addr", "")),
                    sale.get("to", sale.get("to_addr", "")),
                    float(sale.get("price", 0)),
                    sale.get("type", sale.get("sale_type", "buy")),
                    int(sale.get("timestamp", sale.get("created_at", 0))),
                ),
            )
            self.conn.commit()

    def get_nft_sales(self, limit: int = 100) -> List[Dict]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM nft_sales ORDER BY created_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
            return [
                {
                    "token_id": r["token_id"],
                    "from": r["from_addr"],
                    "to": r["to_addr"],
                    "price": r["price"],
                    "type": r["sale_type"],
                    "timestamp": r["created_at"],
                }
                for r in rows
            ]

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
