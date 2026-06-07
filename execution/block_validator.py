# execution/block_validator.py
"""
Block Validator — validates blocks before import
"""

import hashlib
import json
from typing import Dict, Any, Optional


class BlockValidator:
    """Validates blocks for consensus and execution"""
    
    def __init__(self, state_engine, mempool):
        self.state = state_engine
        self.mempool = mempool
    
    def validate_block(self, block: dict, parent_block: Optional[dict] = None) -> tuple[bool, str]:
        """
        Validate block before execution
        Returns: (is_valid, error_message)
        """
        # Check basic structure
        required_fields = ["number", "parent_hash", "timestamp", "proposer", "transactions"]
        for field in required_fields:
            if field not in block:
                return False, f"Missing field: {field}"
        
        # Check parent exists (if not genesis)
        if block["number"] > 0 and not parent_block:
            return False, "Parent block not found"
        
        # Check parent hash matches
        if parent_block and block["parent_hash"] != parent_block.get("hash"):
            return False, "Parent hash mismatch"
        
        # Check block number sequential
        if parent_block and block["number"] != parent_block.get("number", -1) + 1:
            return False, f"Invalid block number: {block['number']}"
        
        # Validate timestamp (not in future)
        import time
        if block["timestamp"] > int(time.time()) + 60:
            return False, "Timestamp too far in future"
        
        if parent_block and block["timestamp"] <= parent_block.get("timestamp", 0):
            return False, "Timestamp not increasing"
        
        # Validate transactions
        for tx in block.get("transactions", []):
            valid, msg = self._validate_transaction(tx)
            if not valid:
                return False, f"Invalid transaction {tx.get('hash')}: {msg}"
        
        # Validate tx_root matches
        computed_root = self._compute_tx_root(block["transactions"])
        if computed_root != block.get("tx_root"):
            return False, f"Tx root mismatch: expected {computed_root}"
        
        return True, ""
    
    def _validate_transaction(self, tx: dict) -> tuple[bool, str]:
        """Validate single transaction"""
        # Check required fields
        required = ["hash", "from", "to", "value", "nonce"]
        for field in required:
            if field not in tx:
                return False, f"Missing field: {field}"
        
        # Check positive value
        if tx["value"] < 0:
            return False, "Negative value"
        
        # Check sender balance (if we have state)
        balance = self.state.get_balance(tx["from"])
        if balance < tx["value"]:
            return False, "Insufficient balance"
        
        # Check nonce
        expected_nonce = self.state.get_nonce(tx["from"])
        if tx["nonce"] != expected_nonce:
            return False, f"Invalid nonce: expected {expected_nonce}"
        
        return True, ""
    
    def _compute_tx_root(self, transactions: list) -> str:
        """Compute transaction merkle root"""
        if not transactions:
            return hashlib.sha256(b"empty_tx").hexdigest()[:32]
        
        tx_hashes = [tx.get("hash", "") for tx in transactions]
        combined = "".join(sorted(tx_hashes))
        return hashlib.sha256(combined.encode()).hexdigest()[:32]
    
    def validate_state_root(self, block: dict, computed_root: str) -> bool:
        """Validate state root after execution"""
        expected = block.get("state_root")
        return expected == computed_root
    
    def validate_block_hash(self, block: dict) -> bool:
        """Validate block hash matches content"""
        computed = self._compute_block_hash(block)
        return computed == block.get("hash")
    
    def _compute_block_hash(self, block: dict) -> str:
        block_data = json.dumps({
            "number": block["number"],
            "parent_hash": block["parent_hash"],
            "timestamp": block["timestamp"],
            "proposer": block.get("proposer", ""),
            "tx_root": block.get("tx_root", ""),
            "state_root": block.get("state_root", "")
        }, sort_keys=True)
        return hashlib.sha256(block_data.encode()).hexdigest()[:32]

