# abi/contract_examples.py
"""Example smart contracts for Mini-EVM"""

from execution.contract_manager import ContractManager


class SimpleCounter:
    """Simple counter contract"""
    
    @staticmethod
    def get_bytecode():
        return [
            ("PUSH", 0),      # initial value
            ("PUSH", 0x100),  # storage key
            ("SSTORE", None), # store
            # increment function
            ("PUSH", 0x100),  # load counter
            ("SLOAD", None),
            ("PUSH", 1),
            ("ADD", None),    # increment
            ("PUSH", 0x100),
            ("SSTORE", None), # store back
            # return
            ("RETURN", None)
        ]
    
    @staticmethod
    def deploy(manager: ContractManager, address: str):
        return manager.deploy(SimpleCounter.get_bytecode(), address)


class Token:
    """Simple token contract"""
    
    @staticmethod
    def get_bytecode():
        return [
            # constructor: set owner
            ("PUSH", 0), ("PUSH", 0x200), ("SSTORE", None),
            # mint function
            ("PUSH", 1000), ("PUSH", 0x300), ("SSTORE", None),
            # transfer function stub
            ("PUSH", 0), ("PUSH", 0x400), ("SSTORE", None),
            ("RETURN", None)
        ]
    
    @staticmethod
    def deploy(manager: ContractManager, address: str):
        return manager.deploy(Token.get_bytecode(), address)


def deploy_all_examples(manager: ContractManager):
    """Deploy all example contracts"""
    contracts = {}
    
    counter_addr = "0xcounter_001"
    if SimpleCounter.deploy(manager, counter_addr):
        contracts["counter"] = counter_addr
        print(f"   ✅ Counter deployed: {counter_addr}")
    
    token_addr = "0xtoken_001"
    if Token.deploy(manager, token_addr):
        contracts["token"] = token_addr
        print(f"   ✅ Token deployed: {token_addr}")
    
    return contracts


if __name__ == "__main__":
    manager = ContractManager()
    print("Deploying example contracts...")
    deploy_all_examples(manager)
    print(f"\n📊 Stats: {manager.get_stats()}")
