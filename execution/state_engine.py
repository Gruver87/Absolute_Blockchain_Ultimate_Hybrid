# execution/state_engine.py
"""
State Engine — deterministic state transition function
Core of blockchain execution
"""

import hashlib
import json
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import copy


@dataclass
class AccountState:
    """State of a single account"""
    balance: int
    nonce: int
    code_hash: str = ""
    storage_root: str = ""


@dataclass
class BlockState:
    """Complete blockchain state"""
    accounts: Dict[str, AccountState]
    block_number: int
    block_hash: str
    parent_hash: str
    state_root: str
    timestamp: int
    
    def to_dict(self) -> dict:
        return {
            "accounts": {
                addr: {
                    "balance": acc.balance,
                    "nonce": acc.nonce,
                    "code_hash": acc.code_hash
                }
                for addr, acc in self.accounts.items()
            },
            "block_number": self.block_number,
            "block_hash": self.block_hash,
            "parent_hash": self.parent_hash,
            "state_root": self.state_root,
            "timestamp": self.timestamp
        }


class StateEngine:
    """
    Deterministic state transition engine
    state -> apply block -> new state
    """
    
    def __init__(self):
        self.state: Optional[BlockState] = None
        self.genesis_alloc: Dict[str, int] = {}
    
    def create_genesis(self, alloc: Dict[str, int] = None) -> BlockState:
        """Create genesis block state"""
        accounts = {}
        alloc = alloc or {"foundation": 1000000, "validator": 100000}
        
        for addr, balance in alloc.items():
            accounts[addr] = AccountState(balance=balance, nonce=0)
        
        self.state = BlockState(
            accounts=accounts,
            block_number=0,
            block_hash=self._compute_genesis_hash(),
            parent_hash="0" * 64,
            state_root=self._compute_state_root(accounts),
            timestamp=int(time.time())
        )
        
        return self.state
    
    def _compute_state_root(self, accounts: Dict[str, AccountState]) -> str:
        """Compute merkle root of all account states"""
        state_data = json.dumps({
            addr: {"balance": acc.balance, "nonce": acc.nonce}
            for addr, acc in accounts.items()
        }, sort_keys=True)
        return hashlib.sha256(state_data.encode()).hexdigest()[:32]
    
    def _compute_genesis_hash(self) -> str:
        return hashlib.sha256(b"genesis_absolute_chain").hexdigest()[:32]
    
    def transition(self, block: dict) -> BlockState:
        """
        Apply block to current state → new state
        This is the CORE function of the blockchain
        """
        if not self.state:
            raise Exception("No state initialized")
        
        # Copy current state
        new_accounts = copy.deepcopy(self.state.accounts)
        
        # Apply each transaction
        for tx in block.get("transactions", []):
            self._apply_transaction(new_accounts, tx)
        
        # Create new state
        new_state = BlockState(
            accounts=new_accounts,
            block_number=block["number"],
            block_hash=block["hash"],
            parent_hash=block["parent_hash"],
            state_root=self._compute_state_root(new_accounts),
            timestamp=block["timestamp"]
        )
        
        # Update current state
        self.state = new_state
        
        return new_state
    
    def _apply_transaction(self, accounts: Dict[str, AccountState], tx: dict):
        """Apply single transaction to state"""
        from_addr = tx.get("from", tx.get("from_addr"))
        to_addr = tx.get("to", tx.get("to_addr"))
        amount = tx.get("amount", tx.get("value", 0))
        
        # Check sender exists
        if from_addr not in accounts:
            accounts[from_addr] = AccountState(balance=0, nonce=0)
        
        # Check balance
        if accounts[from_addr].balance < amount:
            raise Exception(f"Insufficient balance: {from_addr}")
        
        # Check nonce
        expected_nonce = accounts[from_addr].nonce
        tx_nonce = tx.get("nonce", expected_nonce)
        if tx_nonce != expected_nonce:
            raise Exception(f"Invalid nonce: expected {expected_nonce}, got {tx_nonce}")
        
        # Transfer
        accounts[from_addr].balance -= amount
        accounts[from_addr].nonce += 1
        
        if to_addr not in accounts:
            accounts[to_addr] = AccountState(balance=0, nonce=0)
        accounts[to_addr].balance += amount
    
    def get_balance(self, address: str) -> int:
        """Get current balance"""
        if not self.state:
            return 0
        acc = self.state.accounts.get(address)
        return acc.balance if acc else 0
    
    def get_nonce(self, address: str) -> int:
        """Get current nonce"""
        if not self.state:
            return 0
        acc = self.state.accounts.get(address)
        return acc.nonce if acc else 0
    
    def get_state_root(self) -> str:
        return self.state.state_root if self.state else ""
    
    def copy(self) -> "StateEngine":
        """Create a copy for fork processing"""
        new_engine = StateEngine()
        if self.state:
            new_engine.state = copy.deepcopy(self.state)
        return new_engine
    
    def commit_block(self, block: dict) -> BlockState:
        """Alias for transition"""
        return self.transition(block)
