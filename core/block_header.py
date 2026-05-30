# core/block_header.py
"""
Block header with Merkle root
"""

from dataclasses import dataclass
import hashlib
import json
from typing import List, Dict, Optional
from crypto.merkle import merkle_root


@dataclass
class BlockHeader:
    """Block header for light client"""
    number: int
    parent_hash: str
    timestamp: int
    proposer: str
    state_root: str
    tx_root: str
    gas_used: int
    gas_limit: int

    def hash(self) -> str:
        """Compute block header hash"""
        data = {
            "number": self.number,
            "parent_hash": self.parent_hash,
            "timestamp": self.timestamp,
            "proposer": self.proposer,
            "state_root": self.state_root,
            "tx_root": self.tx_root,
            "gas_used": self.gas_used,
            "gas_limit": self.gas_limit
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "parent_hash": self.parent_hash,
            "timestamp": self.timestamp,
            "proposer": self.proposer,
            "state_root": self.state_root,
            "tx_root": self.tx_root,
            "gas_used": self.gas_used,
            "gas_limit": self.gas_limit,
            "hash": self.hash()
        }


class FullBlock:
    """Full block with transactions"""
    def __init__(self, header: BlockHeader, transactions: List[Dict]):
        self.header = header
        self.transactions = transactions

    def compute_tx_root(self) -> str:
        """Compute Merkle root from transactions"""
        if not self.transactions:
            return merkle_root([])
        return merkle_root([json.dumps(tx, sort_keys=True) for tx in self.transactions])

    @staticmethod
    def create(number: int, parent_hash: str, proposer: str, state_root: str,
               transactions: List[Dict], gas_limit: int = 30_000_000) -> "FullBlock":
        """Create a new block"""
        import time
        block = FullBlock(
            header=BlockHeader(
                number=number,
                parent_hash=parent_hash,
                timestamp=int(time.time()),
                proposer=proposer,
                state_root=state_root,
                tx_root="",
                gas_used=0,
                gas_limit=gas_limit
            ),
            transactions=transactions
        )
        # Set tx_root after computing
        block.header.tx_root = block.compute_tx_root()
        block.header.gas_used = sum(tx.get("gas", 21000) for tx in transactions)
        return block

    def get_header(self) -> BlockHeader:
        return self.header
