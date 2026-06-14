"""
ContractManager — deploy and execute MiniVM smart contracts.
Persists to SQLite when a Database is provided.
"""

import time
from typing import Dict, List, Tuple, Optional, Any
from execution.vm import MiniVM


class ContractManager:
    """Manages deployed MiniVM contracts with optional DB persistence."""

    def __init__(self, db=None):
        self.contracts: Dict[str, dict] = {}
        self.vm = MiniVM()
        self._db = db
        if db and hasattr(db, "load_minivm_contracts"):
            for row in db.load_minivm_contracts():
                self.contracts[row["address"]] = {
                    "bytecode": row.get("bytecode") or [],
                    "storage": row.get("storage") or {},
                    "deployed_at": row.get("deployed_at", 0),
                    "calls": row.get("calls", 0),
                }

    def _persist(self, address: str) -> None:
        if not self._db or address not in self.contracts:
            return
        c = self.contracts[address]
        if hasattr(self._db, "save_minivm_contract"):
            self._db.save_minivm_contract(
                address, c["bytecode"], c["storage"], c.get("calls", 0)
            )

    def deploy(self, bytecode: List[Tuple[str, Optional[int]]], address: str,
               initial_storage: Dict[int, int] = None) -> bool:
        """Deploy a new contract at address."""
        if address in self.contracts:
            return False
        self.contracts[address] = {
            "bytecode": bytecode,
            "storage": initial_storage or {},
            "deployed_at": time.time(),
            "calls": 0,
        }
        self._persist(address)
        return True

    def call(self, address: str, method: str, args: List[int]) -> Optional[Dict]:
        """Call a contract method with arguments pushed onto the stack."""
        if address not in self.contracts:
            return None

        contract = self.contracts[address]
        self.vm.reset()

        # Restore persistent storage
        self.vm.storage = contract["storage"].copy()

        # Push args then run bytecode
        bytecode = contract["bytecode"].copy()
        for arg in reversed(args):
            bytecode.insert(0, ("PUSH", arg))
        bytecode.append(("STOP", None))

        result = self.vm.execute(bytecode)

        # Persist storage changes
        contract["storage"] = self.vm.storage.copy()
        contract["calls"] += 1
        self._persist(address)

        return {
            "success":     result.get("success", False),
            "gas_used":    result.get("gas_used", 0),
            "stack":       result.get("stack", []),
            "return_data": result.get("return_data", None),
            "storage":     contract["storage"],
        }

    def get_storage(self, address: str, key: int) -> int:
        if address not in self.contracts:
            return 0
        return self.contracts[address]["storage"].get(key, 0)

    def get_contracts(self) -> dict:
        return self.contracts

    def get_stats(self) -> dict:
        return {
            "total_contracts": len(self.contracts),
            "addresses": list(self.contracts.keys()),
            "total_calls": sum(c["calls"] for c in self.contracts.values()),
            "persisted": self._db is not None,
        }
