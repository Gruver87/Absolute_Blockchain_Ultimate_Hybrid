# execution/contract_manager.py
<<<<<<< HEAD
from typing import Dict, List, Tuple, Optional, Any
from execution.vm import MiniVM

class ContractManager:
=======
"""
Contract Manager - Deploy and execute smart contracts
"""

from typing import Dict, List, Tuple, Optional, Any
from execution.vm import MiniVM
import time


class ContractManager:
    """Manages deployed contracts"""
    
>>>>>>> e1325e33910593a6992287e350ec884bed59f946
    def __init__(self):
        self.contracts: Dict[str, dict] = {}
        self.vm = MiniVM()
    
<<<<<<< HEAD
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
=======
    def deploy(self, bytecode: List[Tuple[str, Optional[int]]], address: str, 
               initial_storage: Dict[int, int] = None) -> bool:
        """Deploy a new contract"""
        if address in self.contracts:
            return False
        
        self.contracts[address] = {
            "bytecode": bytecode,
            "storage": initial_storage or {},
            "deployed_at": time.time(),
            "calls": 0
        }
        return True
    
    def call(self, address: str, method: str, args: List[int]) -> Optional[Dict]:
        """Call a contract method"""
>>>>>>> e1325e33910593a6992287e350ec884bed59f946
        if address not in self.contracts:
            return None
        
        contract = self.contracts[address]
        self.vm.reset()
        
<<<<<<< HEAD
=======
        # Restore storage
        self.vm.storage = contract["storage"].copy()
        
        # Build bytecode with arguments
>>>>>>> e1325e33910593a6992287e350ec884bed59f946
        bytecode = contract["bytecode"].copy()
        for arg in reversed(args):
            bytecode.insert(0, ("PUSH", arg))
        bytecode.append(("STOP", None))
        
<<<<<<< HEAD
        result = self.vm.execute(bytecode)
        contract["storage"] = self.vm.storage.copy()
=======
        # Execute
        result = self.vm.execute(bytecode)
        
        # Save storage changes
        contract["storage"] = self.vm.storage.copy()
        contract["calls"] += 1
>>>>>>> e1325e33910593a6992287e350ec884bed59f946
        
        return {
            "success": result["success"],
            "gas_used": result["gas_used"],
            "stack": result["stack"],
<<<<<<< HEAD
            "storage": result["storage"]
        }
    
    def get_contracts(self) -> Dict:
        return self.contracts
    
    def get_stats(self) -> Dict:
        return {"contracts": len(self.contracts), "addresses": list(self.contracts.keys())}
=======
            "return_data": result["return_data"]
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
            "total_calls": sum(c["calls"] for c in self.contracts.values())
        }
>>>>>>> e1325e33910593a6992287e350ec884bed59f946
