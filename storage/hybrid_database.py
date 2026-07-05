#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hybrid storage: RocksDB hot path + SQLite aux for optional features."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from storage import keycodec as kc
from storage.database import Database as SqliteDatabase
from storage.rocks_store import RocksChainStore


class HybridDatabase:
    """Production store — RocksDB chain/state + SQLite aux.db for cold tables."""

    engine = "rocksdb_hybrid"

    def __init__(self, config: Any):
        chain_path = config.db_path
        aux_path = os.path.join(chain_path, "aux.db")
        rocks_sync = getattr(config, "rocksdb_sync", "FULL")
        sqlite_sync = getattr(config, "sqlite_synchronous", "NORMAL")
        self.db_path = chain_path
        self.synchronous = rocks_sync
        self._core = RocksChainStore(chain_path, synchronous=rocks_sync)
        self._aux = SqliteDatabase(aux_path, synchronous=sqlite_sync)
        self._aux.initialize()

    @property
    def conn(self):
        """Aux SQLite connection (bridge_locks and legacy SQL helpers)."""
        return self._aux.conn

    def initialize(self) -> None:
        self._core.initialize()
        self._migrate_aux_bridge_once()

    def _migrate_aux_bridge_once(self) -> None:
        if self._core.get_meta("aux_bridge_migrated_v1"):
            return
        with self._core.atomic():
            for row in self._aux.get_bridge_locks(limit=1_000_000):
                tx_hash = row.get("tx_hash", "") or ""
                if not tx_hash or self._core._raw_get(kc.key_bridge_lock(tx_hash)):
                    continue
                self._core._raw_put(
                    kc.key_bridge_lock(tx_hash),
                    json.dumps(row, ensure_ascii=False).encode("utf-8"),
                )
            for row in self._aux.conn.execute("SELECT * FROM bridge_credits").fetchall():
                credit = dict(row)
                credit_key = credit.get("credit_key", "") or ""
                if not credit_key or self._core.has_bridge_credit(credit_key):
                    continue
                self._core._raw_put(
                    kc.key_bridge_credit(credit_key),
                    json.dumps(credit, ensure_ascii=False).encode("utf-8"),
                )
            self._core.set_meta("aux_bridge_migrated_v1", True)

    def close(self) -> None:
        self._core.close()
        self._aux.close()

    def backup_to(self, dest_path: str) -> bool:
        return self._core.backup_to(dest_path)

    @contextmanager
    def atomic(self):
        with self._core.atomic():
            yield self

    # ── core delegation ───────────────────────────────────────────────────

    def set_meta(self, key: str, value: Any) -> None:
        self._core.set_meta(key, value)

    def get_meta(self, key: str, default: Any = None) -> Any:
        return self._core.get_meta(key, default)

    def save_block(self, block: Dict) -> bool:
        return self._core.save_block(block)

    def persist_block_atomic(
        self,
        block: Dict,
        transactions: List[Dict],
        burned_amount: float = 0.0,
        burn_address: str = "",
    ) -> bool:
        return self._core.persist_block_atomic(block, transactions, burned_amount, burn_address)

    def _persist_block_locked(
        self,
        block: Dict,
        transactions: List[Dict],
        burned_amount: float = 0.0,
        burn_address: str = "",
    ) -> None:
        self._core._persist_block_locked(block, transactions, burned_amount, burn_address)

    def get_block(self, height: int) -> Optional[Dict]:
        return self._core.get_block(height)

    def get_block_by_hash(self, block_hash: str) -> Optional[Dict]:
        return self._core.get_block_by_hash(block_hash)

    def get_latest_blocks(self, limit: int = 20) -> List[Dict]:
        return self._core.get_latest_blocks(limit)

    def get_chain_tip(self) -> int:
        return self._core.get_chain_tip()

    def get_last_block(self) -> Optional[Dict]:
        return self._core.get_last_block()

    def get_all_accounts(self) -> List[Dict]:
        return self._core.get_all_accounts()

    def compute_state_root(self) -> str:
        return self._core.compute_state_root()

    def get_live_state_root_meta(self) -> tuple[str, int]:
        if hasattr(self._core, "get_live_state_root_meta"):
            return self._core.get_live_state_root_meta()
        return "", -1

    def get_balance(self, address: str) -> float:
        return self._core.get_balance(address)

    def get_nonce(self, address: str) -> int:
        return self._core.get_nonce(address)

    def get_account(self, address: str) -> Optional[Dict]:
        return self._core.get_account(address)

    def update_balance(self, address: str, delta: float) -> float:
        return self._core.update_balance(address, delta)

    def set_balance(self, address: str, balance: float) -> None:
        self._core.set_balance(address, balance)

    def balance_delta(self, address: str, delta: float) -> None:
        self._core.balance_delta(address, delta)

    def increment_nonce(self, address: str) -> int:
        return self._core.increment_nonce(address)

    def nonce_increment(self, address: str) -> int:
        return self._core.nonce_increment(address)

    def save_account(
        self,
        address: str,
        balance: float = 0.0,
        nonce: int = 0,
        code: str | None = None,
        storage: str | None = None,
    ) -> None:
        self._core.save_account(address, balance, nonce, code, storage)

    def update_account_storage(self, address: str, storage: Dict) -> None:
        self._core.update_account_storage(address, storage)

    def save_validator(self, address: str, stake: float) -> None:
        self._core.save_validator(address, stake)

    def get_validators(self, active_only: bool = True) -> List[Dict]:
        return self._core.get_validators(active_only)

    def slash_validator(self, address: str) -> None:
        self._core.slash_validator(address)

    def save_transaction(self, tx: Dict) -> bool:
        return self._core.save_transaction(tx)

    def get_transaction(self, tx_hash: str) -> Optional[Dict]:
        return self._core.get_transaction(tx_hash)

    def get_transactions_in_block(self, height: int) -> List[Dict]:
        return self._core.get_transactions_in_block(height)

    def get_recent_transactions(self, limit: int = 30) -> List[Dict]:
        return self._core.get_recent_transactions(limit)

    def get_tx_receipt(self, tx_hash: str) -> Optional[Dict]:
        return self._core.get_tx_receipt(tx_hash)

    def get_receipts_by_block(self, block_height: int) -> List[Dict]:
        return self._core.get_receipts_by_block(block_height)

    def get_transactions_by_address(
        self,
        address: str,
        limit: int = 50,
        offset: int = 0,
        direction: str = "all",
    ) -> List[Dict]:
        return self._core.get_transactions_by_address(address, limit, offset, direction)

    def count_transactions_by_address(self, address: str, direction: str = "all") -> int:
        return self._core.count_transactions_by_address(address, direction)

    def get_address_activity(self, address: str) -> Dict:
        return self._core.get_address_activity(address)

    def get_proposer_audit_log(
        self,
        limit: int = 50,
        offset: int = 0,
        proposer: str = "",
    ) -> List[Dict]:
        return self._core.get_proposer_audit_log(limit, offset, proposer)

    def record_burn(self, block_height: int, burned_amount: float) -> None:
        self._core.record_burn(block_height, burned_amount)

    def get_total_burned(self) -> float:
        return self._core.get_total_burned()

    def get_burn_stats(self) -> Dict:
        return self._core.get_burn_stats()

    def reorg_truncate_above(self, height: int) -> None:
        self._core.reorg_truncate_above(height)

    def truncate_chain_state(self, height: int) -> int:
        return self._core.truncate_chain_state(height)

    def truncate_blocks_above(self, height: int) -> int:
        return self._core.truncate_blocks_above(height)

    def truncate_all_blocks(self) -> int:
        return self._core.truncate_all_blocks()

    def reset_accounts_from_alloc(self, alloc: Dict[str, float], *, _in_atomic: bool = False) -> None:
        self._core.reset_accounts_from_alloc(alloc, _in_atomic=_in_atomic)

    def get_total_supply(self) -> float:
        return self._core.get_total_supply()

    def get_stats(self) -> Dict:
        stats = self._core.get_stats()
        stats["aux_path"] = os.path.join(self.db_path, "aux.db")
        return stats

    def record_state_root_mismatch(self, *args: Any, **kwargs: Any) -> None:
        self._core.record_state_root_mismatch(*args, **kwargs)

    def get_state_root_mismatches(self, limit: int = 20) -> List[Dict]:
        if hasattr(self._core, "get_state_root_mismatches"):
            return self._core.get_state_root_mismatches(limit=limit)
        return self._aux.get_state_root_mismatches(limit=limit)

    def record_tx_propagation_event(self, *args: Any, **kwargs: Any) -> None:
        self._core.record_tx_propagation_event(*args, **kwargs)

    def save_slash_event(self, validator: str, reason: str, epoch: int, penalty: int) -> None:
        self._core.save_slash_event(validator, reason, epoch, penalty)

    def get_slash_events(self, limit: int = 100) -> List[Dict]:
        return self._core.get_slash_events(limit)

    def get_chain_metrics(self, window: int = 32) -> Dict:
        return self._core.get_chain_metrics(window)

    # ── bridge (Rocks core — not aux.db) ─────────────────────────────────

    def save_bridge_lock(
        self,
        from_addr: str,
        to_chain: str,
        to_addr: str,
        amount: float,
        tx_hash: str,
    ) -> None:
        self._core.save_bridge_lock(from_addr, to_chain, to_addr, amount, tx_hash)

    def confirm_bridge_lock(self, tx_hash: str) -> None:
        self._core.confirm_bridge_lock(tx_hash)

    def get_bridge_locks(self, limit: int = 50) -> List[Dict]:
        return self._core.get_bridge_locks(limit)

    @staticmethod
    def bridge_credit_key(l1_tx_hash: str, recipient: str, amount: float, from_chain: str) -> str:
        return RocksChainStore.bridge_credit_key(l1_tx_hash, recipient, amount, from_chain)

    def has_bridge_credit(self, credit_key: str) -> bool:
        return self._core.has_bridge_credit(credit_key)

    def save_bridge_credit(
        self, l1_tx_hash: str, recipient: str, amount: float, from_chain: str
    ) -> str:
        return self._core.save_bridge_credit(l1_tx_hash, recipient, amount, from_chain)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._aux, name)
