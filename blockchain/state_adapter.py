# blockchain/state_adapter.py
"""Adapter: Database -> TransactionValidator state interface."""

from dataclasses import dataclass
from typing import Optional

SATOSHI_MULTIPLIER = 1_000_000


@dataclass
class AccountView:
    address: str
    balance: float
    nonce: int


class DatabaseStateAdapter:
    """Exposes Database balances/nonces to TransactionValidator."""

    def __init__(self, db):
        self.db = db

    def get_account(self, address: str) -> Optional[AccountView]:
        row = self.db.get_account(address)
        if row:
            return AccountView(
                address=address,
                balance=float(row.get("balance", 0)),
                nonce=int(row.get("nonce", 0)),
            )
        return AccountView(address=address, balance=0.0, nonce=0)

    def get_balance_satoshi(self, address: str) -> int:
        return int(self.db.get_balance(address) * SATOSHI_MULTIPLIER)
