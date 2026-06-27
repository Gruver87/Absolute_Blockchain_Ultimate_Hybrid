# -*- coding: utf-8 -*-
"""Execution mempool compatibility layer for legacy tests."""
import hashlib
import time
from dataclasses import dataclass
from typing import Dict, List, Union

from blockchain.mempool import Mempool as _BaseMempool, MempoolTransaction


@dataclass
class Transaction:
    sender: str
    recipient: str
    amount: float
    gas_price: float = 1.0
    nonce: int = 0
    hash: str = ""

    def __post_init__(self):
        if not self.hash:
            raw = f"{self.sender}{self.recipient}{self.amount}{self.nonce}{self.gas_price}"
            self.hash = "0x" + hashlib.sha256(raw.encode()).hexdigest()[:40]


def create_transaction(
    sender: str,
    recipient: str,
    amount: float,
    gas_price: float = 1.0,
    nonce: int = 0,
) -> Transaction:
    return Transaction(sender, recipient, amount, gas_price, nonce)


class Mempool(_BaseMempool):
    def add_transaction(self, tx: Union[Transaction, Dict]) -> Union[bool, str]:
        if isinstance(tx, dict):
            sender = tx.get("from", tx.get("from_addr", ""))
            recipient = tx.get("to", tx.get("to_addr", ""))
            amount = float(tx.get("value", tx.get("amount", 0)))
            nonce = int(tx.get("nonce", 0))
            fee = float(tx.get("gas_price", tx.get("gasPrice", tx.get("fee", 1))))
            tx_hash = tx.get("hash") or (
                "0x" + hashlib.sha256(f"{sender}{recipient}{amount}{nonce}".encode()).hexdigest()
            )
            mempool_tx = MempoolTransaction(
                tx_hash=tx_hash,
                from_addr=sender,
                to_addr=recipient,
                amount=amount,
                fee=fee,
                nonce=nonce,
                timestamp=time.time(),
            )
            if self.add_raw(mempool_tx):
                return tx_hash
            return False

        mempool_tx = MempoolTransaction(
            tx_hash=tx.hash,
            from_addr=tx.sender,
            to_addr=tx.recipient,
            amount=tx.amount,
            fee=tx.gas_price,
            nonce=tx.nonce,
            timestamp=time.time(),
        )
        return self.add_raw(mempool_tx)

    def get_pending_count(self) -> int:
        return self.get_size()

    def get_transactions_for_block(self, limit: int = 100) -> List[Dict]:
        return self.get_sorted_transactions()[:limit]
