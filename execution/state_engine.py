# execution/state_engine.py
"""
State Engine — deterministic in-memory state transitions.

Account balances are stored as integer satoshi (1 ABS = 1_000_000).
create_genesis / transition accept ABS amounts on the wire and convert via
runtime.amount.to_satoshi.

Canonical L1 consensus root remains DB/Rocks via compute_db_state_root —
this engine is an auxiliary deterministic sandbox, not the P2P tip root.
"""

from __future__ import annotations

import copy
import hashlib
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from execution.state_root import compute_state_engine_root
from runtime.amount import from_satoshi, from_satoshi_float, to_satoshi


@dataclass
class AccountState:
    """State of a single account (balance in satoshi)."""

    balance: int  # satoshi
    nonce: int
    code_hash: str = ""
    storage_root: str = ""


@dataclass
class BlockState:
    """Complete in-memory block state."""

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
                    "balance_satoshi": acc.balance,
                    "balance": float(from_satoshi(acc.balance)),
                    "nonce": acc.nonce,
                    "code_hash": acc.code_hash,
                }
                for addr, acc in self.accounts.items()
            },
            "block_number": self.block_number,
            "block_hash": self.block_hash,
            "parent_hash": self.parent_hash,
            "state_root": self.state_root,
            "timestamp": self.timestamp,
        }


class StateEngine:
    """Deterministic state transition engine: state -> apply block -> new state."""

    def __init__(self, db=None):
        # db accepted for call-site compatibility (main.py); tip root stays on DB/Rocks
        self.db = db
        self.state: Optional[BlockState] = None
        self.genesis_alloc: Dict[str, int] = {}

    def create_genesis(self, alloc: Dict[str, Any] = None) -> BlockState:
        """Create genesis. ``alloc`` values are ABS amounts."""
        accounts: Dict[str, AccountState] = {}
        alloc = alloc or {"foundation": 1000000, "validator": 100000}

        for addr, balance_abs in alloc.items():
            accounts[addr] = AccountState(balance=to_satoshi(balance_abs), nonce=0)

        self.genesis_alloc = {addr: to_satoshi(bal) for addr, bal in alloc.items()}

        self.state = BlockState(
            accounts=accounts,
            block_number=0,
            block_hash=self._compute_genesis_hash(),
            parent_hash="0" * 64,
            state_root=self._compute_state_root(accounts),
            timestamp=int(time.time()),
        )
        return self.state

    def _compute_state_root(self, accounts: Dict[str, AccountState]) -> str:
        return compute_state_engine_root(accounts)

    def _compute_genesis_hash(self) -> str:
        return hashlib.sha256(b"genesis_absolute_chain").hexdigest()[:32]

    def transition(self, block: dict) -> BlockState:
        if not self.state:
            raise Exception("No state initialized")

        new_accounts = copy.deepcopy(self.state.accounts)
        for tx in block.get("transactions", []):
            self._apply_transaction(new_accounts, tx)

        new_state = BlockState(
            accounts=new_accounts,
            block_number=block["number"],
            block_hash=block["hash"],
            parent_hash=block["parent_hash"],
            state_root=self._compute_state_root(new_accounts),
            timestamp=block["timestamp"],
        )
        self.state = new_state
        return new_state

    def _apply_transaction(self, accounts: Dict[str, AccountState], tx: dict) -> None:
        from_addr = tx.get("from", tx.get("from_addr"))
        to_addr = tx.get("to", tx.get("to_addr"))
        if "amount_satoshi" in tx:
            amount_sat = max(0, int(tx["amount_satoshi"]))
        else:
            amount_sat = to_satoshi(tx.get("amount", tx.get("value", 0)))
        if "fee_satoshi" in tx:
            fee_sat = max(0, int(tx["fee_satoshi"]))
        else:
            fee_sat = to_satoshi(tx.get("fee", 0) or 0)

        if from_addr not in accounts:
            accounts[from_addr] = AccountState(balance=0, nonce=0)

        total = amount_sat + fee_sat
        if accounts[from_addr].balance < total:
            raise Exception(f"Insufficient balance: {from_addr}")

        expected_nonce = accounts[from_addr].nonce
        tx_nonce = tx.get("nonce", expected_nonce)
        if tx_nonce != expected_nonce:
            raise Exception(f"Invalid nonce: expected {expected_nonce}, got {tx_nonce}")

        accounts[from_addr].balance -= total
        accounts[from_addr].nonce += 1

        if to_addr not in accounts:
            accounts[to_addr] = AccountState(balance=0, nonce=0)
        accounts[to_addr].balance += amount_sat

    def get_balance_satoshi(self, address: str) -> int:
        if not self.state:
            return 0
        acc = self.state.accounts.get(address)
        return int(acc.balance) if acc else 0

    def get_balance(self, address: str) -> int:
        """Legacy whole ABS (floor). Prefer get_balance_satoshi / get_balance_abs."""
        return int(from_satoshi(self.get_balance_satoshi(address)))

    def get_balance_abs(self, address: str) -> float:
        return from_satoshi_float(self.get_balance_satoshi(address))

    def get_nonce(self, address: str) -> int:
        if not self.state:
            return 0
        acc = self.state.accounts.get(address)
        return acc.nonce if acc else 0

    def get_state_root(self) -> str:
        return self.state.state_root if self.state else ""

    def copy(self) -> "StateEngine":
        new_engine = StateEngine(db=self.db)
        if self.state:
            new_engine.state = copy.deepcopy(self.state)
        return new_engine

    def commit_block(self, block: dict) -> BlockState:
        return self.transition(block)
