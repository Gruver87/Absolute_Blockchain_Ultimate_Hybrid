#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Block headers for SPV / light client verification.
"""

import hashlib
import json
import time
from typing import List, Dict, Optional, Any

from crypto.merkle import merkle_root


class BlockHeader:
    """Заголовок блока — хранится в light client без полных транзакций."""

    def __init__(
        self,
        number: int,
        parent_hash: str,
        proposer: str,
        state_root: str,
        tx_root: str,
        timestamp: int = 0,
        extra_data: str = "",
        block_hash: str = "",
    ):
        self.number = number
        self.parent_hash = parent_hash
        self.proposer = proposer
        self.state_root = state_root
        self.tx_root = tx_root
        self.timestamp = timestamp or int(time.time())
        self.extra_data = extra_data
        self._block_hash = block_hash

    def hash(self) -> str:
        if self._block_hash:
            return self._block_hash
        raw = (
            f"{self.number}{self.parent_hash}{self.proposer}"
            f"{self.state_root}{self.tx_root}{self.timestamp}{self.extra_data}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "number": self.number,
            "parent_hash": self.parent_hash,
            "proposer": self.proposer,
            "state_root": self.state_root,
            "tx_root": self.tx_root,
            "timestamp": self.timestamp,
            "extra_data": self.extra_data,
            "hash": self.hash(),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BlockHeader":
        return cls(
            number=int(d.get("number", d.get("height", 0))),
            parent_hash=d.get("parent_hash", ""),
            proposer=d.get("proposer", d.get("miner", "")),
            state_root=d.get("state_root", ""),
            tx_root=d.get("tx_root", d.get("transactions_root", "")),
            timestamp=int(d.get("timestamp", 0)),
            extra_data=d.get("extra_data", ""),
            block_hash=d.get("hash", d.get("block_hash", "")),
        )

    @classmethod
    def from_block_dict(cls, block_dict: Dict[str, Any]) -> "BlockHeader":
        """Создаёт заголовок из полного блока (core.Block.to_dict или DB row)."""
        txs = block_dict.get("transactions") or []
        tx_items = []
        for tx in txs:
            if isinstance(tx, dict):
                if "hash" in tx:
                    tx_items.append(tx["hash"])
                else:
                    tx_items.append(json.dumps(tx, sort_keys=True))
            else:
                tx_items.append(str(tx))
        root = merkle_root(tx_items) if tx_items else merkle_root(["empty"])
        return cls(
            number=int(block_dict.get("height", block_dict.get("number", 0))),
            parent_hash=block_dict.get("parent_hash", ""),
            proposer=block_dict.get("miner", block_dict.get("proposer", "")),
            state_root=block_dict.get("state_root", ""),
            tx_root=block_dict.get("tx_root") or root,
            timestamp=int(block_dict.get("timestamp", 0)),
            extra_data=block_dict.get("extra_data", ""),
            block_hash=block_dict.get("hash", block_dict.get("block_hash", "")),
        )


class FullBlock:
    """Полный блок с заголовком и транзакциями (для тестов и SPV API)."""

    def __init__(self, header: BlockHeader, transactions: List[Dict]):
        self.header = header
        self.transactions = transactions

    @classmethod
    def create(
        cls,
        number: int,
        parent_hash: str,
        proposer: str,
        state_root: str,
        transactions: List[Dict],
    ) -> "FullBlock":
        tx_strings = [json.dumps(tx, sort_keys=True) for tx in transactions]
        tx_root = merkle_root(tx_strings) if tx_strings else merkle_root(["empty"])
        header = BlockHeader(
            number=number,
            parent_hash=parent_hash,
            proposer=proposer,
            state_root=state_root,
            tx_root=tx_root,
        )
        return cls(header, transactions)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **self.header.to_dict(),
            "transactions": self.transactions,
        }
