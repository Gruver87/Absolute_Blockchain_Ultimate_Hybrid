#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mempool — пул неподтверждённых транзакций с приоритетом по комиссии.

Интегрирует:
  - Базовая сортировка по fee (System A)
  - Валидация адресов и сумм через middleware/validators.py
  - ECDSA проверка подписи через crypto/wallet.py
"""

import time
import threading
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

# --- Input validation (middleware/validators.py) ---
try:
    from middleware.validators import validate_address, validate_amount, validate_tx_data
    _VALIDATORS_AVAILABLE = True
except ImportError:
    _VALIDATORS_AVAILABLE = False

# --- ECDSA signature verification (crypto/wallet.py) ---
try:
    from crypto.wallet import verify_transaction_signature
    _ECDSA_AVAILABLE = True
except ImportError:
    _ECDSA_AVAILABLE = False


@dataclass
class MempoolTransaction:
    """Транзакция в мемпуле."""
    tx_hash: str
    from_addr: str
    to_addr: str
    amount: float
    fee: float
    nonce: int = 0
    signature: str = ""
    public_key: str = ""
    data: str = ""
    gas: int = 21_000
    timestamp: float = field(default_factory=time.time)

    def has_valid_signature(self) -> bool:
        """ECDSA check; when require_signatures is on, empty signature fails."""
        require = getattr(self, "require_signatures", False)
        if not self.signature:
            return not require
        if not self.public_key:
            return False
        if not _ECDSA_AVAILABLE:
            return False
        try:
            tx_dict = {
                "from": self.from_addr,
                "to": self.to_addr,
                "value": int(self.amount) if self.amount == int(self.amount) else self.amount,
                "nonce": self.nonce,
                "chain_id": getattr(self, "_chain_id", None) or getattr(self, "chain_id", 1),
                "signature": self.signature,
                "public_key": self.public_key,
                "data": self.data or "",
            }
            return verify_transaction_signature(tx_dict)
        except Exception:
            return False


def _validate_mempool_tx(tx: MempoolTransaction, min_fee: float) -> Tuple[bool, str]:
    """
    Полная валидация транзакции перед добавлением в мемпул.
    Использует middleware/validators.py если доступен.
    """
    if not tx.tx_hash:
        return False, "missing_hash"
    if tx.fee < min_fee:
        return False, f"fee_too_low (min={min_fee:.8f})"

    if _VALIDATORS_AVAILABLE:
        # Validate addresses
        valid, err = validate_address(tx.from_addr)
        if not valid:
            # Allow non-0x addresses (internal/genesis) with basic check
            if len(tx.from_addr) < 5:
                return False, f"invalid_from: {err}"

        valid, err = validate_address(tx.to_addr)
        if not valid:
            if len(tx.to_addr) < 5:
                return False, f"invalid_to: {err}"

        # Validate amount
        valid, err = validate_amount(tx.amount, min_amount=0.0)
        if not valid:
            return False, f"invalid_amount: {err}"

    if tx.amount < 0:
        return False, "negative_amount"

    return True, "ok"


class Mempool:
    """Пул транзакций с сортировкой по комиссии и полной валидацией."""

    def __init__(self, max_size: int = 10000, min_fee: float = 0.0001):
        self.transactions: Dict[str, MempoolTransaction] = {}
        self.max_size = max_size
        self.min_fee = min_fee
        self.lock = threading.RLock()
        self._rejected_count = 0
        self.blockchain = None
        self.chain_id = 1
        self.require_signatures = False

    def set_blockchain(self, blockchain) -> None:
        """Attach live chain for nonce/balance/signature checks."""
        self.blockchain = blockchain
        if blockchain and getattr(blockchain, "config", None):
            self.chain_id = blockchain.config.chain_id
            self.require_signatures = getattr(
                blockchain.config, "require_signatures", False
            )

    def add(self, tx: MempoolTransaction) -> bool:
        """Добавить транзакцию с полной валидацией."""
        with self.lock:
            if tx.tx_hash in self.transactions:
                return False

            # Full validation
            valid, reason = _validate_mempool_tx(tx, self.min_fee)
            if not valid:
                self._rejected_count += 1
                return False

            tx._chain_id = self.chain_id

            # ECDSA signature check
            if not tx.has_valid_signature():
                self._rejected_count += 1
                return False

            if self.blockchain:
                from core.blockchain import Transaction
                chain_tx = Transaction(
                    from_addr=tx.from_addr,
                    to_addr=tx.to_addr,
                    value=tx.amount,
                    nonce=tx.nonce,
                    gas=self.blockchain.config.base_gas_price,
                    tx_hash=tx.tx_hash,
                    signature=tx.signature,
                    public_key=tx.public_key,
                )
                tx._chain_id = self.chain_id
                check = self.blockchain.validate_transaction(chain_tx)
                if not check.get("valid"):
                    self._rejected_count += 1
                    return False

            if len(self.transactions) >= self.max_size:
                self._cleanup()
            self.transactions[tx.tx_hash] = tx
            return True

    def add_raw(self, tx: MempoolTransaction) -> bool:
        """Добавить транзакцию без строгой валидации адресов (для internal/genesis txs)."""
        with self.lock:
            if tx.tx_hash in self.transactions:
                return False
            if tx.fee < self.min_fee:
                return False
            if len(self.transactions) >= self.max_size:
                self._cleanup()
            self.transactions[tx.tx_hash] = tx
            return True

    def get(self, limit: int = 100, min_fee: float = 0) -> List[MempoolTransaction]:
        """Получить транзакции для майнинга (сортировка по комиссии)."""
        with self.lock:
            sorted_txs = sorted(
                self.transactions.values(),
                key=lambda x: x.fee,
                reverse=True
            )
            return [tx for tx in sorted_txs if tx.fee >= min_fee][:limit]

    def get_sorted_transactions(self) -> List[Dict]:
        """Возвращает транзакции в формате dict (для BlockBuilder System C)."""
        with self.lock:
            sorted_txs = sorted(
                self.transactions.values(),
                key=lambda x: x.fee,
                reverse=True
            )
            return [
                {
                    "hash": tx.tx_hash,
                    "from": tx.from_addr,
                    "to": tx.to_addr,
                    "value": tx.amount,
                    "gasPrice": tx.fee,
                    "gas": tx.gas or 21000,
                    "nonce": tx.nonce,
                    "data": tx.data or "",
                    "timestamp": tx.timestamp,
                }
                for tx in sorted_txs
            ]

    def remove(self, tx_hash: str) -> bool:
        """Удалить транзакцию."""
        with self.lock:
            return self.transactions.pop(tx_hash, None) is not None

    def has_transaction(self, tx_hash: str) -> bool:
        with self.lock:
            return tx_hash in self.transactions

    def get_size(self) -> int:
        with self.lock:
            return len(self.transactions)

    def get_stats(self) -> dict:
        with self.lock:
            if not self.transactions:
                return {"size": 0, "total_fees": 0, "avg_fee": 0, "rejected": self._rejected_count}
            fees = [tx.fee for tx in self.transactions.values()]
            return {
                "size": len(self.transactions),
                "total_fees": sum(fees),
                "avg_fee": sum(fees) / len(fees),
                "rejected": self._rejected_count,
                "validators_available": _VALIDATORS_AVAILABLE,
                "ecdsa_available": _ECDSA_AVAILABLE,
            }

    def _cleanup(self):
        """Удалить 10% самых дешёвых транзакций."""
        if len(self.transactions) < self.max_size * 0.8:
            return
        sorted_txs = sorted(self.transactions.values(), key=lambda x: x.fee)
        to_remove = int(len(self.transactions) * 0.1)
        for tx in sorted_txs[:to_remove]:
            del self.transactions[tx.tx_hash]
