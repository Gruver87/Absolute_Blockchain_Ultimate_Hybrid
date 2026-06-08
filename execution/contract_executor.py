# execution/contract_executor.py
"""
Contract Executor — выполнение ABI-контрактов через VM
"""

from typing import Dict, Any, Optional, List
from execution.vm import MiniVM
from execution.contracts import ContractRegistry


class ContractExecutor:
    """Исполняет методы контрактов по ABI"""
    
    def __init__(self, registry: ContractRegistry):
        self.registry = registry
        self.last_gas_used = 0
    
    def call_contract(
        self, 
        address: str, 
        method: str, 
        args: List[int] = None,
        readonly: bool = True
    ) -> Dict[str, Any]:
        """
        Вызвать метод контракта
        
        Args:
            address: адрес контракта
            method: имя метода из ABI
            args: аргументы метода
            readonly: если True — не сохранять изменения storage
        
        Returns:
            результат выполнения
        """
        contract = self.registry.get_contract(address)
        if not contract:
            return {"success": False, "error": "Contract not found"}
        
        # Получаем байткод метода из ABI
        abi = self.registry.get_abi(address, method)
        if not abi:
            return {"success": False, "error": f"Method {method} not found in ABI"}
        
        # Создаём VM с копией storage
        vm = MiniVM()
        if readonly:
            vm.storage = contract["storage"].copy()
        else:
            vm.storage = contract["storage"]
        
        # Собираем байткод для выполнения
        bytecode = list(abi)  # копируем байткод метода
        
        # Добавляем аргументы (PUSH в обратном порядке)
        if args:
            for arg in reversed(args):
                bytecode.insert(0, ("PUSH", arg))
        
        # Добавляем STOP
        bytecode.append(("STOP", None))
        
        # Выполняем
        try:
            result = vm.execute(bytecode)
            self.last_gas_used = result["gas_used"]
            
            # Если не readonly — сохраняем изменения
            if not readonly:
                contract["storage"] = vm.storage
            
            return {
                "success": result["success"],
                "gas_used": result["gas_used"],
                "stack": result["stack"],
                "storage": result["storage"],
                "return_value": result["stack"][-1] if result["stack"] else None
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def deploy_contract(
        self, 
        address: str, 
        bytecode: list, 
        abi: dict = None,
        deployer: str = "foundation"
    ) -> bool:
        """Деплой нового контракта"""
        return self.registry.deploy(address, bytecode, abi)
    
    def get_storage_at(self, address: str, key: int) -> int:
        """Получить значение из storage (как eth_getStorageAt)"""
        return self.registry.get_storage(address, key)
    
    def get_contract_abi(self, address: str) -> dict:
        """Получить полный ABI контракта"""
        return self.registry.get_abi(address)
