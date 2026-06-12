# execution/contracts.py
"""
Contract Registry — хранилище деплоеных контрактов
"""

from typing import Dict, Any, Optional
import time


class ContractRegistry:
    """Реестр смарт-контрактов"""
    
    def __init__(self):
        self.contracts: Dict[str, Dict[str, Any]] = {}
    
    def deploy(self, address: str, bytecode: list, abi: dict = None) -> bool:
        """Деплой нового контракта"""
        if address in self.contracts:
            return False
        
        self.contracts[address] = {
            "bytecode": bytecode,
            "storage": {},
            "abi": abi or {},
            "deployed_at": time.time(),
            "deployer": "foundation"
        }
        return True
    
    def get_contract(self, address: str) -> Optional[Dict]:
        """Получить контракт по адресу"""
        return self.contracts.get(address)
    
    def get_storage(self, address: str, key: int) -> int:
        """Получить значение из storage контракта"""
        contract = self.contracts.get(address)
        if not contract:
            return 0
        return contract["storage"].get(key, 0)
    
    def set_storage(self, address: str, key: int, value: int) -> bool:
        """Установить значение в storage контракта"""
        contract = self.contracts.get(address)
        if not contract:
            return False
        contract["storage"][key] = value
        return True
    
    def get_abi(self, address: str, method: str = None):
        """Получить ABI контракта или конкретного метода"""
        contract = self.contracts.get(address)
        if not contract:
            return None
        if method:
            return contract["abi"].get(method)
        return contract["abi"]
    
    def list_contracts(self) -> list:
        """Список всех контрактов"""
        return list(self.contracts.keys())
    
    def get_stats(self) -> dict:
        return {
            "total_contracts": len(self.contracts),
            "addresses": list(self.contracts.keys())
        }
