# execution/block_builder.py
"""
Block Builder — creates blocks from mempool transactions
"""

import hashlib
import time
from typing import List, Dict, Any, Optional


class BlockBuilder:
    """Builds blocks with deterministic ordering"""
    
    def __init__(self, mempool, state_engine):
        self.mempool = mempool
        self.state = state_engine
    
    def build_block(self, parent_block: dict, proposer: str = "validator") -> dict:
        """
        Build a new block from mempool transactions
        """
        # Get pending transactions
        pending_txs = self.mempool.get_sorted_transactions()
        
        # Filter valid transactions (check balances)
        valid_txs = []
        for tx in pending_txs:
            balance = self.state.get_balance(tx["from"])
            if balance >= tx["value"] + (tx["gasPrice"] * tx["gas"]):
                valid_txs.append(tx)
        
        # Limit block size
        max_txs = 100
        selected_txs = valid_txs[:max_txs]
        
        # Calculate block number
        block_number = parent_block.get("number", 0) + 1
        
        # Build transaction trie root
        tx_root = self._compute_tx_root(selected_txs)
        
        # Create block
        block = {
            "number": block_number,
            "parent_hash": parent_block.get("hash", "0" * 64),
            "timestamp": int(time.time()),
            "proposer": proposer,
            "transactions": [self._tx_to_dict(tx) for tx in selected_txs],
            "tx_root": tx_root,
            "state_root": None,  # Will be filled after execution
            "hash": None,  # Will be filled after execution
        }
        
        return block
    
    def _compute_tx_root(self, transactions) -> str:
        """Compute merkle root of transactions"""
        if not transactions:
            return hashlib.sha256(b"empty_tx").hexdigest()[:32]
        
        tx_strings = [tx["hash"] for tx in transactions]
        combined = "".join(sorted(tx_strings))
        return hashlib.sha256(combined.encode()).hexdigest()[:32]
    
    def _tx_to_dict(self, tx) -> dict:
        """Convert transaction to dict for inclusion in block"""
        return {
            "hash": tx["hash"],
            "from": tx["from"],
            "to": tx["to"],
            "value": tx["value"],
            "gas_limit": tx["gas"],
            "gas_price": tx["gasPrice"],
            "nonce": tx["nonce"],
            "data": tx.data.hex() if isinstance(tx.data, bytes) else tx.data,
            "timestamp": tx.timestamp
        }
    
    def finalize_block(self, block: dict, state_root: str) -> dict:
        """Finalize block with state root and hash"""
        block["state_root"] = state_root
        block["hash"] = self._compute_block_hash(block)
        return block
    
    def _compute_block_hash(self, block: dict) -> str:
        """Compute deterministic block hash"""
        block_data = json.dumps({
            "number": block["number"],
            "parent_hash": block["parent_hash"],
            "timestamp": block["timestamp"],
            "proposer": block["proposer"],
            "tx_root": block["tx_root"],
            "state_root": block["state_root"]
        }, sort_keys=True)
        return hashlib.sha256(block_data.encode()).hexdigest()[:32]


import json

