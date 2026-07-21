#!/usr/bin/env python3
"""Explicit dev/test cross-chain bridge adapter.

Production transfers use ``RustBridge``. This adapter is intentionally local
and in-memory for development scenarios that opt in through configuration.
"""

from crypto import native
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict


class Chain(Enum):
    ETHEREUM = "ethereum"
    BSC = "bsc"
    SOLANA = "solana"
    ABSOLUTE = "absolute"


@dataclass
class BridgeTransaction:
    tx_hash: str
    from_chain: str
    to_chain: str
    from_addr: str
    to_addr: str
    amount: float
    status: str = "pending"
    timestamp: int = 0


class DevBridgeAdapter:
    """Local dev/test bridge adapter between supported chain labels."""

    def __init__(self):
        self.transactions: Dict[str, BridgeTransaction] = {}
        self.fees = {
            Chain.ETHEREUM.value: 0.01,
            Chain.BSC.value: 0.002,
            Chain.SOLANA.value: 0.001,
            Chain.ABSOLUTE.value: 0.005,
        }

    def bridge(
        self,
        from_chain: str,
        to_chain: str,
        from_addr: str,
        to_addr: str,
        amount: float,
    ) -> str:
        """Create a local dev/test transfer record."""
        tx_hash = native.sha256_hex(
            f"{from_chain}{to_chain}{from_addr}{to_addr}{amount}{time.time()}".encode()
        )[:16]

        fee = self.fees.get(from_chain, 0.01)
        net_amount = amount - fee

        self.transactions[tx_hash] = BridgeTransaction(
            tx_hash=tx_hash,
            from_chain=from_chain,
            to_chain=to_chain,
            from_addr=from_addr,
            to_addr=to_addr,
            amount=net_amount,
            status="pending",
            timestamp=int(time.time()),
        )

        return tx_hash

    def confirm_transaction(self, tx_hash: str) -> bool:
        if tx_hash in self.transactions:
            self.transactions[tx_hash].status = "confirmed"
            return True
        return False

    def get_bridge_stats(self) -> Dict:
        total = len(self.transactions)
        confirmed = sum(1 for tx in self.transactions.values() if tx.status == "confirmed")

        return {
            "total_transactions": total,
            "confirmed": confirmed,
            "pending": total - confirmed,
            "total_value": sum(tx.amount for tx in self.transactions.values()),
            "supported_chains": [c.value for c in Chain],
            "adapter": "dev-test",
        }

    def estimate_fee(self, from_chain: str, amount: float) -> float:
        return self.fees.get(from_chain, 0.01) * amount


# Compatibility class name used by older code paths.
CrossChainBridge = DevBridgeAdapter
