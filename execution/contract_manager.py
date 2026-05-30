# execution/contract_manager.py
"""
Contract manager — deploys and executes smart contracts
"""

from typing import Dict, List, Tuple, Optional, Any
from execution.vm import MiniVM


class ContractManager:
    def __init__(self):
        self.contracts: Dict[str, dict] = {}
        self.vm = MiniVM()

    def deploy(self, bytecode: List[Tuple[str, Optional[int]]], address: str) -> bool:
        if address in self.contracts:
            return False
        self.contracts[address] = {
            "bytecode": bytecode,
            "storage": {},
            "deployed_at": __import__("time").time()
        }
        return True

    def call(self, address: str, function: str, args: List[int]) -> Optional[Dict]:
        if address not in self.contracts:
            return None

        contract = self.contracts[address]
        self.vm.reset()

        bytecode = contract["bytecode"].copy()
        for arg in reversed(args):
            bytecode.insert(0, ("PUSH", arg))
        bytecode.append(("STOP", None))

        result = self.vm.execute(bytecode)
        contract["storage"] = self.vm.storage.copy()

        return {
            "success": result["success"],
            "gas_used": result["gas_used"],
            "stack": result["stack"],
            "storage": result["storage"]
        }

    def get_contracts(self) -> dict:
        return self.contracts
