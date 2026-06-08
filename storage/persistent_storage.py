# storage/persistent_storage.py
"""
Persistent storage with crash recovery and snapshots
"""

import json
import os
import shutil
import time
from typing import Dict, List, Optional, Any
from datetime import datetime

from storage.database import BlockchainDB


class PersistentStorage:
    """High-level persistent storage with recovery"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.db = BlockchainDB(f"{data_dir}/blockchain.db")
        self.snapshots_dir = f"{data_dir}/snapshots"
        os.makedirs(self.snapshots_dir, exist_ok=True)
    
    def save_block(self, block: dict) -> bool:
        """Save block to persistent storage"""
        return self.db.save_block(block)
    
    def get_block(self, block_hash: str) -> Optional[dict]:
        """Get block by hash"""
        return self.db.get_block(block_hash)
    
    def get_block_by_number(self, number: int) -> Optional[dict]:
        """Get block by number"""
        return self.db.get_block_by_number(number)
    
    def get_latest_block(self) -> Optional[dict]:
        """Get latest canonical block"""
        return self.db.get_latest_block()
    
    def get_latest_block_number(self) -> int:
        """Get latest block number"""
        return self.db.get_latest_block_number()
    
    def save_account_state(self, address: str, balance: int, nonce: int = 0) -> bool:
        """Save account state"""
        return self.db.save_account(address, balance, nonce)
    
    def get_account_state(self, address: str) -> dict:
        """Get account state"""
        account = self.db.get_account(address)
        if account:
            return account
        return {"address": address, "balance": 0, "nonce": 0}
    
    def get_balance(self, address: str) -> int:
        """Get account balance"""
        return self.db.get_balance(address)
    
    def update_balance(self, address: str, delta: int) -> bool:
        """Update account balance atomically"""
        current = self.get_balance(address)
        nonce = self.get_nonce(address)
        return self.db.save_account(address, current + delta, nonce + 1)
    
    def get_nonce(self, address: str) -> int:
        """Get account nonce"""
        account = self.db.get_account(address)
        return account["nonce"] if account else 0
    
    def save_validator(self, address: str, stake: int) -> bool:
        """Save validator"""
        return self.db.save_validator(address, stake)
    
    def get_validators(self) -> List[dict]:
        """Get all validators"""
        return self.db.get_validators()
    
    def save_transaction_receipt(self, tx_hash: str, receipt: dict) -> bool:
        """Save transaction receipt"""
        return self.db.save_transaction_receipt(tx_hash, receipt)
    
    # ========== FIX: ADDED MISSING METHODS ==========
    
    def save_metadata(self, key: str, value: str) -> bool:
        """Save metadata to database"""
        return self.db.save_metadata(key, value)
    
    def get_metadata(self, key: str) -> Optional[str]:
        """Get metadata from database"""
        return self.db.get_metadata(key)
    
    def save_checkpoint(self, block_hash: str, height: int, snapshot: dict) -> bool:
        """Save checkpoint"""
        return self.db.save_checkpoint(block_hash, height, snapshot)
    
    def get_latest_checkpoint(self) -> Optional[dict]:
        """Get latest checkpoint"""
        return self.db.get_latest_checkpoint()
    
    # ========== END FIX ==========
    
    def create_snapshot(self, block_hash: str, height: int) -> bool:
        """Create a full state snapshot"""
        snapshot = {
            "block_hash": block_hash,
            "height": height,
            "timestamp": datetime.now().isoformat(),
            "accounts": {}
        }
        return self.save_checkpoint(block_hash, height, snapshot)
    
    def restore_from_snapshot(self) -> Optional[dict]:
        """Restore latest snapshot"""
        checkpoint = self.get_latest_checkpoint()
        if checkpoint:
            return checkpoint["snapshot"]
        return None
    
    def recover_from_crash(self) -> bool:
        """Recover after crash - verify database integrity"""
        try:
            self.db.get_latest_block_number()
            print("✅ Database integrity verified")
            return True
        except Exception as e:
            print(f"⚠️ Database corruption detected: {e}")
            return False
    
    def backup(self, backup_dir: str) -> bool:
        """Create database backup"""
        try:
            os.makedirs(backup_dir, exist_ok=True)
            shutil.copy2(self.db.db_path, f"{backup_dir}/blockchain_backup.db")
            print(f"✅ Backup saved to {backup_dir}")
            return True
        except Exception as e:
            print(f"❌ Backup failed: {e}")
            return False
    
    def get_stats(self) -> dict:
        """Get storage statistics"""
        return self.db.get_stats()
    
    def chain_exists(self) -> bool:
        """Check if chain exists"""
        return self.get_latest_block_number() > 0
