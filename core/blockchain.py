#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Absolute Blockchain — ядро цепочки блоков.

Содержит:
  - Transaction     : структура транзакции (c ECDSA подписью)
  - Block           : структура блока (c state_root + canonical hash)
  - Blockchain      : основная логика (burn mechanism, StateEngine, BlockValidator)

Интегрирует из всех трёх систем:
  - System A: Transaction/Block/burn/genesis (основа)
  - System C: StateEngine (детерминированный state_root)
  - blockchain/canonical_serializer.py: детерминированный хэш блока
  - execution/block_validator.py: валидация блоков из P2P
"""

import hashlib
import json
import time
import threading
from typing import List, Dict, Optional, Any

from storage.database import Database
from runtime.config import Config
from runtime.tokenomics import genesis_balances, get_tokenomics_summary, MAX_SUPPLY_ABS
from kernel.event_bus import EventBus

# --- System C: StateEngine (детерминированные state transitions) ---
try:
    from execution.state_engine import StateEngine
    _STATE_ENGINE_AVAILABLE = True
except ImportError:
    _STATE_ENGINE_AVAILABLE = False

# --- CanonicalSerializer (детерминированный хэш) ---
try:
    from blockchain.canonical_serializer import CanonicalSerializer
    _CANONICAL_AVAILABLE = True
except ImportError:
    _CANONICAL_AVAILABLE = False

# --- BlockValidator (валидация P2P-блоков) ---
try:
    from execution.block_validator import BlockValidator
    _BLOCK_VALIDATOR_AVAILABLE = True
except ImportError:
    _BLOCK_VALIDATOR_AVAILABLE = False


# ── Структуры данных ─────────────────────────────────────────────────────────

class Transaction:
    """Транзакция в сети Absolute (с поддержкой ECDSA-подписи)."""

    def __init__(
        self,
        from_addr: str,
        to_addr: str,
        value: float,
        nonce: int = 0,
        gas: int = 21_000,
        data: str = "",
        tx_hash: str = "",
        signature: str = "",
        public_key: str = "",
        timestamp: int = 0,
    ):
        self.from_addr = from_addr
        self.to_addr = to_addr
        self.value = value
        self.nonce = nonce
        self.gas = gas
        self.data = data
        self.signature = signature
        self.public_key = public_key
        self.timestamp = timestamp or int(time.time())
        self.hash = tx_hash or self._compute_hash()

        # Заполняется при включении в блок
        self.block_height: int = 0
        self.gas_used: int = gas
        self.fee: float = 0.0
        self.burned: float = 0.0

    def _compute_hash(self) -> str:
        raw = f"{self.from_addr}{self.to_addr}{self.value}{self.nonce}{self.gas}{self.data}{self.timestamp}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def to_dict(self) -> Dict:
        return {
            "hash": self.hash,
            "from_addr": self.from_addr,
            "to_addr": self.to_addr,
            "value": self.value,
            "nonce": self.nonce,
            "gas": self.gas,
            "gas_used": self.gas_used,
            "fee": self.fee,
            "burned": self.burned,
            "data": self.data,
            "signature": self.signature,
            "public_key": self.public_key,
            "timestamp": self.timestamp,
            "block_height": self.block_height,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "Transaction":
        tx = cls(
            from_addr=d.get("from_addr", d.get("from", "")),
            to_addr=d.get("to_addr", d.get("to", "")),
            value=float(d.get("value", d.get("amount", 0))),
            nonce=int(d.get("nonce", 0)),
            gas=int(d.get("gas", 21_000)),
            data=d.get("data", d.get("tx_data", "")),
            tx_hash=d.get("hash", d.get("tx_hash", "")),
            signature=d.get("signature", ""),
            public_key=d.get("public_key", ""),
            timestamp=int(d.get("timestamp", 0)),
        )
        tx.fee = float(d.get("fee", 0.0))
        tx.burned = float(d.get("burned", 0.0))
        tx.block_height = int(d.get("block_height", 0))
        return tx

    def __repr__(self) -> str:
        return f"Tx({self.hash[:10]}... {self.from_addr[:8]}->{self.to_addr[:8]} {self.value} ABS)"


class Block:
    """Блок в цепочке Absolute (с state_root и canonical hash)."""

    def __init__(
        self,
        height: int,
        parent_hash: str,
        miner: str,
        transactions: Optional[List[Transaction]] = None,
        timestamp: int = 0,
        block_hash: str = "",
        extra_data: str = "",
        state_root: str = "",
    ):
        self.height = height
        self.parent_hash = parent_hash
        self.miner = miner
        self.transactions: List[Transaction] = transactions or []
        self.timestamp = timestamp or int(time.time())
        self.extra_data = extra_data
        self.state_root = state_root  # deterministic state root (System C)
        self.tx_root = self._compute_tx_root()

        # Вычисляемые поля
        self.tx_count = len(self.transactions)
        self.gas_used: int = sum(tx.gas_used for tx in self.transactions)
        self.total_burned: float = sum(tx.burned for tx in self.transactions)

        self.hash = block_hash or self._compute_hash()

    def _compute_tx_root(self) -> str:
        """Merkle root транзакций блока (для SPV / light client)."""
        try:
            from crypto.merkle import merkle_root
            items = [tx.hash for tx in self.transactions] if self.transactions else []
            return merkle_root(items) if items else merkle_root(["empty"])
        except Exception:
            return hashlib.sha256(b"empty").hexdigest()

    def _compute_hash(self) -> str:
        """Детерминированный хэш блока через CanonicalSerializer."""
        if _CANONICAL_AVAILABLE:
            try:
                block_dict = {
                    "height": self.height,
                    "parent_hash": self.parent_hash,
                    "miner": self.miner,
                    "timestamp": self.timestamp,
                    "extra_data": self.extra_data,
                    "state_root": self.state_root,
                    "transactions": [
                        {"hash": tx.hash, "from": tx.from_addr, "to": tx.to_addr,
                         "amount": tx.value, "fee": tx.fee, "nonce": tx.nonce,
                         "timestamp": tx.timestamp}
                        for tx in sorted(self.transactions, key=lambda t: t.hash)
                    ],
                }
                canonical = CanonicalSerializer.serialize(block_dict)
                return hashlib.sha256(canonical.encode()).hexdigest()
            except Exception:
                pass

        # Fallback: simple hash
        tx_hashes = "".join(tx.hash for tx in self.transactions)
        raw = (
            f"{self.height}{self.parent_hash}{self.miner}"
            f"{self.timestamp}{tx_hashes}{self.extra_data}{self.state_root}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    def to_dict(self) -> Dict:
        return {
            "height": self.height,
            "hash": self.hash,
            "parent_hash": self.parent_hash,
            "miner": self.miner,
            "timestamp": self.timestamp,
            "tx_count": self.tx_count,
            "gas_used": self.gas_used,
            "total_burned": self.total_burned,
            "extra_data": self.extra_data,
            "state_root": self.state_root,
            "tx_root": self.tx_root,
            "transactions": [tx.to_dict() for tx in self.transactions],
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "Block":
        txs = [Transaction.from_dict(t) for t in d.get("transactions", [])]
        blk = cls(
            height=d["height"],
            parent_hash=d["parent_hash"],
            miner=d["miner"],
            transactions=txs,
            timestamp=d.get("timestamp", 0),
            block_hash=d.get("hash", d.get("block_hash", "")),
            extra_data=d.get("extra_data", ""),
            state_root=d.get("state_root", ""),
        )
        blk.total_burned = float(d.get("total_burned", 0.0))
        return blk

    def __repr__(self) -> str:
        return (
            f"Block(#{self.height} hash={self.hash[:10]}... "
            f"txs={self.tx_count} burned={self.total_burned:.4f})"
        )


# ── Основная логика ───────────────────────────────────────────────────────────

class Blockchain:
    """
    Ядро блокчейна: создание/добавление блоков, применение транзакций,
    механизм сжигания, genesis.

    Включает:
    - StateEngine (System C) для детерминированного state_root
    - BlockValidator (System C) для валидации P2P-блоков
    - CanonicalSerializer для детерминированного хэша
    """

    GENESIS_HASH = "0" * 64

    def __init__(self, config: Config, db: Database, bus: Optional[EventBus] = None):
        self.config = config
        self.db = db
        self.bus = bus
        self.lock = threading.RLock()

        # --- System C: StateEngine ---
        if _STATE_ENGINE_AVAILABLE:
            self.state_engine = StateEngine()
            self._init_state_engine()
            print("[Blockchain] StateEngine: enabled (deterministic state_root)")
        else:
            self.state_engine = None

        # --- System C: BlockValidator ---
        if _BLOCK_VALIDATOR_AVAILABLE and self.state_engine:
            self.block_validator = BlockValidator(self.state_engine, None)
            print("[Blockchain] BlockValidator: enabled")
        else:
            self.block_validator = None

        self.pool_locks = None  # runtime.pool_locks.PoolLockManager

        self._ensure_genesis()

    def _init_state_engine(self):
        """Инициализирует StateEngine из данных genesis или текущего состояния БД."""
        if not self.state_engine:
            return
        founder = (
            getattr(self.config, "founder_address", "")
            or self.config.miner_address
            or ""
        )
        genesis_alloc = genesis_balances(founder or None)
        if self.config.miner_address and self.config.miner_address not in genesis_alloc:
            genesis_alloc[self.config.miner_address] = int(
                getattr(self.config, "min_stake", 1000)
            )
        self.state_engine.create_genesis(genesis_alloc)

    # ── Genesis ──────────────────────────────────────────────────────────────

    def _ensure_genesis(self):
        if self.db.get_chain_tip() == 0 and self.db.get_last_block() is None:
            founder = (
                getattr(self.config, "founder_address", "")
                or self.config.miner_address
                or ""
            )
            alloc = genesis_balances(founder or None)
            state_root = self.state_engine.get_state_root() if self.state_engine else ""
            initials = getattr(self.config, "founder_initials", "D.U.P.")
            genesis = Block(
                height=0,
                parent_hash=self.GENESIS_HASH,
                miner="genesis",
                timestamp=int(time.time()),
                extra_data=(
                    f"{self.config.network_name} Genesis | "
                    f"max_supply={MAX_SUPPLY_ABS:,} ABS | founder={initials} {self.config.founder_percent}%"
                ),
                state_root=state_root,
            )
            self.db.save_block(genesis.to_dict())
            total_minted = 0.0
            for addr, amount in alloc.items():
                self.db.set_balance(addr, float(amount))
                total_minted += amount
            # Сохраняем метаданные токеномики
            try:
                self.db.set_meta("tokenomics", get_tokenomics_summary(founder or None))
            except Exception:
                pass
            print(
                f"[Blockchain] Genesis block created "
                f"(minted={total_minted:,.0f} {self.config.coin_symbol}, "
                f"max_supply={MAX_SUPPLY_ABS:,}, founder={initials} "
                f"{getattr(self.config, 'founder_percent', 17.4)}%)"
            )

    # ── Создание блока ───────────────────────────────────────────────────────

    def create_block(self, transactions: List[Transaction], proposer: str) -> Block:
        """Собирает новый блок из транзакций и текущего tip."""
        with self.lock:
            last = self.db.get_last_block()
            height = last["height"] + 1 if last else 1
            parent_hash = last["hash"] if last else self.GENESIS_HASH

            # Применяем транзакции, считаем burn
            applied_txs = []
            block_burned = 0.0

            for tx in transactions:
                result = self._apply_transaction(tx, height)
                if result["success"]:
                    applied_txs.append(tx)
                    block_burned += tx.burned

            # Начисляем block reward майнеру (не выше max supply)
            current_supply = self.db.get_total_supply()
            max_supply = float(getattr(self.config, "max_supply", MAX_SUPPLY_ABS))
            reward = self.config.block_reward
            if current_supply + reward > max_supply:
                reward = max(0.0, max_supply - current_supply)
            if reward > 0:
                self.db.update_balance(proposer, reward)

            # Вычисляем state_root через StateEngine (System C)
            state_root = ""
            if self.state_engine:
                try:
                    block_dict = {
                        "number": height,
                        "hash": "pending",
                        "parent_hash": parent_hash,
                        "timestamp": int(time.time()),
                        "transactions": [
                            {
                                "from": tx.from_addr,
                                "to": tx.to_addr,
                                "amount": tx.value,
                                "nonce": tx.nonce,
                            }
                            for tx in applied_txs
                        ],
                    }
                    new_state = self.state_engine.transition(block_dict)
                    state_root = new_state.state_root
                except Exception:
                    state_root = ""

            block = Block(
                height=height,
                parent_hash=parent_hash,
                miner=proposer,
                transactions=applied_txs,
                extra_data=f"v{self.config.node_version}",
                state_root=state_root,
            )
            return block

    # ── Добавление блока ─────────────────────────────────────────────────────

    def add_block(self, block: Block) -> bool:
        """Сохраняет блок в БД атомарно, эмитит событие."""
        with self.lock:
            tx_dicts = []
            for tx in block.transactions:
                tx.block_height = block.height
                tx_dicts.append(tx.to_dict())

            success = self.db.persist_block_atomic(
                block.to_dict(),
                tx_dicts,
                burned_amount=block.total_burned,
                burn_address=self.config.burn_address if block.total_burned > 0 else "",
            )
            if not success:
                return False

            if self.bus:
                self.bus.emit("block.new", block.to_dict())

            return True

    def import_block(self, block_dict: Dict) -> bool:
        """
        Импортирует блок от P2P-пира.
        Использует BlockValidator (System C) для проверки.
        """
        with self.lock:
            # Validate using System C BlockValidator if available
            if self.block_validator:
                last = self.db.get_last_block()
                valid, msg = self.block_validator.validate_block(block_dict, last)
                if not valid:
                    return False

            try:
                block = Block.from_dict(block_dict)
                return self.add_block(block)
            except Exception:
                return False

    # ── Применение транзакции ────────────────────────────────────────────────

    def _apply_transaction(self, tx: Transaction, block_height: int) -> Dict:
        """
        Применяет одну транзакцию к состоянию.
        Реализует механизм сжигания: burn_rate% от комиссии уничтожается.
        """
        fee = tx.gas * self.config.gas_price_wei
        burn_amount = fee * self.config.burn_rate
        miner_fee = fee - burn_amount

        sender_balance = self.db.get_balance(tx.from_addr)
        total_cost = tx.value + fee

        if sender_balance < total_cost:
            return {"success": False, "error": "insufficient_funds"}

        if self.pool_locks:
            allowed, reason = self.pool_locks.is_outgoing_allowed(
                tx.from_addr, total_cost, sender_balance
            )
            if not allowed:
                return {"success": False, "error": reason}

        # Списание у отправителя
        self.db.update_balance(tx.from_addr, -total_cost)
        # Зачисление получателю
        self.db.update_balance(tx.to_addr, tx.value)
        # Комиссия майнеру (за вычетом сожжённой части)
        self.db.update_balance(self.config.miner_address or "genesis", miner_fee)

        # Обновляем nonce
        self.db.increment_nonce(tx.from_addr)

        if self.pool_locks:
            self.pool_locks.record_outgoing(tx.from_addr, total_cost)

        # Заполняем поля транзакции
        tx.fee = fee
        tx.burned = burn_amount
        tx.gas_used = tx.gas
        tx.block_height = block_height

        if self.bus:
            self.bus.emit("tx.applied", tx.to_dict())

        return {
            "success": True,
            "fee": fee,
            "burned": burn_amount,
            "miner_fee": miner_fee,
        }

    # ── Валидация ────────────────────────────────────────────────────────────

    def validate_transaction(self, tx: Transaction) -> Dict:
        """Проверяет транзакцию перед добавлением в мемпул."""
        if not tx.from_addr or not tx.to_addr:
            return {"valid": False, "error": "missing_address"}
        if tx.value < 0:
            return {"valid": False, "error": "negative_value"}
        if tx.gas < self.config.base_gas_price:
            return {"valid": False, "error": "gas_too_low"}

        expected_nonce = self.db.get_nonce(tx.from_addr)
        if tx.nonce != expected_nonce:
            return {"valid": False, "error": f"nonce_mismatch (got {tx.nonce}, expected {expected_nonce})"}

        fee = tx.gas * self.config.gas_price_wei
        balance = self.db.get_balance(tx.from_addr)
        total_cost = tx.value + fee
        if balance < total_cost:
            return {"valid": False, "error": "insufficient_funds"}

        if self.pool_locks:
            allowed, reason = self.pool_locks.is_outgoing_allowed(
                tx.from_addr, total_cost, balance
            )
            if not allowed:
                return {"valid": False, "error": reason}

        # Verify ECDSA signature if present
        if tx.signature and tx.public_key:
            try:
                from crypto.wallet import verify_transaction_signature
                tx_dict = {
                    "from": tx.from_addr,
                    "to": tx.to_addr,
                    "value": tx.value,
                    "nonce": tx.nonce,
                    "chain_id": self.config.chain_id,
                    "signature": tx.signature,
                    "public_key": tx.public_key,
                }
                if not verify_transaction_signature(tx_dict):
                    return {"valid": False, "error": "invalid_signature"}
            except Exception:
                pass  # Signature verification optional if ecdsa not installed

        return {"valid": True}

    def validate_block(self, block: Block) -> Dict:
        """Базовая структурная валидация блока (для P2P-синхронизации)."""
        last = self.db.get_last_block()
        if last:
            expected_height = last["height"] + 1
            if block.height != expected_height:
                return {"valid": False, "error": f"height_mismatch (got {block.height}, expected {expected_height})"}
            if block.parent_hash != last["hash"]:
                return {"valid": False, "error": "parent_hash_mismatch"}

        # Проверка хеша
        recomputed = block._compute_hash()
        if block.hash != recomputed:
            return {"valid": False, "error": "invalid_hash"}

        return {"valid": True}

    # ── Публичные геттеры ────────────────────────────────────────────────────

    def get_height(self) -> int:
        return self.db.get_chain_tip()

    def get_balance(self, address: str) -> float:
        return self.db.get_balance(address)

    def get_last_block(self) -> Optional[Dict]:
        return self.db.get_last_block()

    def get_block(self, height: int) -> Optional[Dict]:
        return self.db.get_block(height)

    def get_block_by_hash(self, block_hash: str) -> Optional[Dict]:
        return self.db.get_block_by_hash(block_hash) if hasattr(self.db, "get_block_by_hash") else None

    def get_transaction(self, tx_hash: str) -> Optional[Dict]:
        return self.db.get_transaction(tx_hash)

    def get_state_root(self) -> str:
        """Текущий state root (детерминированный, System C)."""
        if self.state_engine:
            return self.state_engine.get_state_root()
        return ""

    def get_stats(self) -> Dict:
        db_stats = self.db.get_stats()
        burn_stats = self.db.get_burn_stats()
        return {
            **db_stats,
            **burn_stats,
            "coin_symbol": self.config.coin_symbol,
            "chain_id": self.config.chain_id,
            "network": self.config.network_name,
            "max_supply": getattr(self.config, "max_supply", MAX_SUPPLY_ABS),
            "founder_initials": getattr(self.config, "founder_initials", "D.U.P."),
            "founder_percent": getattr(self.config, "founder_percent", 17.4),
            "founder_address": getattr(self.config, "founder_address", ""),
            "state_root": self.get_state_root(),
            "state_engine": self.state_engine is not None,
            "block_validator": self.block_validator is not None,
            "canonical_hash": _CANONICAL_AVAILABLE,
        }
