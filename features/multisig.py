# multisig.py - Multi-signature wallet module
import hashlib
import time
from typing import List, Dict, Any, Set

class MultiSigWallet:
    _registry: Dict[str, "MultiSigWallet"] = {}

    def __init__(self, owners: List[str], required: int):
        unique_owners = []
        for owner in owners or []:
            if owner and owner not in unique_owners:
                unique_owners.append(owner)
        if not unique_owners:
            raise ValueError("at least one owner required")
        if required <= 0 or required > len(unique_owners):
            raise ValueError("required confirmations must be between 1 and owner count")

        self.owners = unique_owners
        self.required = required
        self.wallet_id = hashlib.sha256(
            f"{'|'.join(self.owners)}:{self.required}:{time.time_ns()}".encode()
        ).hexdigest()[:16]
        self.transactions: Dict[str, Dict[str, Any]] = {}
        self.confirmations: Dict[str, Set[str]] = {}
        self._registry[self.wallet_id] = self
    
    def create_transaction(self, to: str, amount: float) -> Dict[str, Any]:
        if not to:
            return {"success": False, "error": "recipient required"}
        if amount <= 0:
            return {"success": False, "error": "amount must be > 0"}

        tx_id = "tx_" + hashlib.sha256(
            f"{self.wallet_id}:{to}:{amount}:{len(self.transactions)}:{time.time_ns()}".encode()
        ).hexdigest()[:24]
        tx = {
            "tx_id": tx_id,
            "to": to,
            "amount": amount,
            "created_at": int(time.time()),
            "status": "pending",
            "executed": False,
            "required": self.required,
            "confirmations": [],
        }
        self.transactions[tx_id] = tx
        self.confirmations[tx_id] = set()
        return {"success": True, "wallet_id": self.wallet_id, **tx}
    
    def confirm(self, tx_id: str, owner: str) -> Dict[str, Any]:
        if owner not in self.owners:
            return {"success": False, "error": "owner not authorized"}
        tx = self.transactions.get(tx_id)
        if not tx:
            return {"success": False, "error": "transaction not found"}
        if tx["executed"]:
            return {"success": False, "error": "transaction already executed"}

        before = len(self.confirmations[tx_id])
        self.confirmations[tx_id].add(owner)
        confirmations = sorted(self.confirmations[tx_id])
        tx["confirmations"] = confirmations
        duplicate = len(confirmations) == before
        if len(confirmations) >= self.required:
            tx["executed"] = True
            tx["status"] = "executed"
        return {
            "success": True,
            "tx_id": tx_id,
            "confirmations": len(confirmations),
            "required": self.required,
            "executed": tx["executed"],
            "duplicate": duplicate,
        }

    def get_transaction(self, tx_id: str) -> Dict[str, Any]:
        tx = self.transactions.get(tx_id)
        return dict(tx) if tx else {}

    def list_transactions(self) -> List[Dict[str, Any]]:
        return [dict(tx) for tx in self.transactions.values()]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wallet_id": self.wallet_id,
            "owners": list(self.owners),
            "required": self.required,
            "pending_transactions": sum(
                1 for tx in self.transactions.values() if not tx["executed"]
            ),
            "executed_transactions": sum(
                1 for tx in self.transactions.values() if tx["executed"]
            ),
        }

    @classmethod
    def list_wallets(cls) -> List[Dict[str, Any]]:
        return [wallet.to_dict() for wallet in cls._registry.values()]

def init():
    return {"success": True, "module": "multisig"}

