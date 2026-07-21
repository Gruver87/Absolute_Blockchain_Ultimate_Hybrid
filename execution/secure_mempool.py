# -*- coding: utf-8 -*-
"""Secure mempool with nonce replay protection for legacy v49 tests."""
import time
from typing import Dict, Tuple, Union

from crypto import native
from execution.mempool import Mempool, MempoolTransaction, Transaction


class SecureMempool(Mempool):
    def __init__(self, state_engine):
        super().__init__()
        self.state_engine = state_engine
        self._seen_nonces: Dict[str, set] = {}

    def add_transaction(self, tx: Union[Dict, Transaction]) -> Tuple[bool, str]:
        if isinstance(tx, dict):
            amount = float(tx.get("value", tx.get("amount", 0)))
            if amount < 0:
                return False, "negative_amount"
            sender = tx.get("from", tx.get("from_addr", ""))
            recipient = tx.get("to", tx.get("to_addr", ""))
            nonce = int(tx.get("nonce", 0))
            fee = float(tx.get("gas_price", tx.get("fee", 1)))
            tx_hash = tx.get("hash") or (
                "0x" + native.sha256_hex(f"{sender}{recipient}{amount}{nonce}".encode())
            )
            seen = self._seen_nonces.setdefault(sender, set())
            if nonce in seen:
                return False, "duplicate_nonce"
            balance = self.state_engine.get_balance(sender) if self.state_engine else 0.0
            if balance < amount:
                return False, "insufficient_balance"
            mempool_tx = MempoolTransaction(
                tx_hash=tx_hash,
                from_addr=sender,
                to_addr=recipient,
                amount=amount,
                fee=fee,
                nonce=nonce,
                signature=tx.get("signature", ""),
                public_key=tx.get("public_key", ""),
                timestamp=time.time(),
            )
            if not self.add_raw(mempool_tx):
                return False, "mempool_rejected"
            seen.add(nonce)
            return True, "ok"

        if tx.amount < 0:
            return False, "negative_amount"
        if not super().add_transaction(tx):
            return False, "mempool_rejected"
        return True, "ok"
