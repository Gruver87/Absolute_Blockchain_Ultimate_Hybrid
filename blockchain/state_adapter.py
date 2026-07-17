# blockchain/state_adapter.py
"""Adapter: Database -> TransactionValidator state interface."""

from dataclasses import dataclass
from typing import Optional

from runtime.amount import account_balance_abs
from runtime.state_truth import canonical_balance_satoshi


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
                balance=account_balance_abs(row),
                nonce=int(row.get("nonce", 0)),
            )
        return AccountView(address=address, balance=0.0, nonce=0)

    def get_balance_satoshi(self, address: str) -> int:
        return canonical_balance_satoshi(self.db, address)
