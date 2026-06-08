#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MINI EVM - Стековая виртуальная машина для смарт-контрактов"""

import json
import hashlib
import time

# Глобальное состояние
state = {
    "balances": {},
    "nonces": {},
    "contracts": {}
}

# Генезис-балансы
state["balances"]["0x40e908721295de4a5cbc775abac8909781aeeea8"] = 1000000
state["nonces"]["0x40e908721295de4a5cbc775abac8909781aeeea8"] = 0

# Opcodes
OPCODES = {
    "PUSH": 1,
    "POP": 2,
    "ADD": 3,
    "SUB": 4,
    "MUL": 5,
    "DIV": 6,
    "STORE": 7,
    "LOAD": 8,
    "TRANSFER": 9,
    "JUMP": 10,
    "JUMPI": 11,
    "STOP": 0
}

class MiniEVM:
    def __init__(self):
        self.stack = []
        self.storage = {}
        self.gas_used = 0
        self.pc = 0
    
    def execute_bytecode(self, bytecode, context=None):
        """Выполнение байткода"""
        self.stack = []
        self.storage = context.get("storage", {}) if context else {}
        self.gas_used = 0
        self.pc = 0
        
        lines = bytecode.strip().split("\n")
        
        while self.pc < len(lines):
            line = lines[self.pc].strip()
            if not line or line.startswith("#"):
                self.pc += 1
                continue
            
            parts = line.split()
            op = parts[0].upper()
            
            self.gas_used += 1
            
            if op == "PUSH":
                if len(parts) < 2:
                    raise Exception("PUSH requires value")
                value = int(parts[1])
                self.stack.append(value)
            
            elif op == "POP":
                self.stack.pop()
            
            elif op == "ADD":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a + b)
            
            elif op == "SUB":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a - b)
            
            elif op == "MUL":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a * b)
            
            elif op == "DIV":
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a // b if b != 0 else 0)
            
            elif op == "STORE":
                if len(parts) < 2:
                    raise Exception("STORE requires key")
                key = parts[1]
                self.storage[key] = self.stack.pop()
            
            elif op == "LOAD":
                if len(parts) < 2:
                    raise Exception("LOAD requires key")
                key = parts[1]
                self.stack.append(self.storage.get(key, 0))
            
            elif op == "TRANSFER":
                if len(parts) < 2:
                    raise Exception("TRANSFER requires to address")
                to_addr = parts[1]
                value = self.stack.pop()
                from_addr = context.get("from", "0x0") if context else "0x0"
                
                global state
                state["balances"].setdefault(from_addr, 0)
                state["balances"].setdefault(to_addr, 0)
                
                if state["balances"][from_addr] < value:
                    raise Exception(f"Insufficient balance: {from_addr}")
                
                state["balances"][from_addr] -= value
                state["balances"][to_addr] += value
            
            elif op == "JUMP":
                if len(parts) < 2:
                    raise Exception("JUMP requires destination")
                dest = int(parts[1])
                if dest < 0 or dest >= len(lines):
                    raise Exception(f"Invalid jump destination: {dest}")
                self.pc = dest
                continue
            
            elif op == "JUMPI":
                if len(parts) < 2:
                    raise Exception("JUMPI requires destination")
                cond = self.stack.pop()
                if cond != 0:
                    dest = int(parts[1])
                    if dest < 0 or dest >= len(lines):
                        raise Exception(f"Invalid jump destination: {dest}")
                    self.pc = dest
                    continue
            
            elif op == "STOP":
                break
            
            else:
                raise Exception(f"Unknown opcode: {op}")
            
            self.pc += 1
        
        result = {
            "stack": self.stack.copy(),
            "storage": self.storage.copy(),
            "gas_used": self.gas_used
        }
        
        if context:
            context["storage"] = self.storage
        
        return result
    
    def get_storage(self, key):
        return self.storage.get(key, 0)
    
    def set_storage(self, key, value):
        self.storage[key] = value

def deploy_contract(from_addr, bytecode):
    """Деплой смарт-контракта"""
    contract_addr = "0x" + hashlib.sha256(f"{from_addr}{time.time()}".encode()).hexdigest()[:40]
    
    state["contracts"][contract_addr] = {
        "owner": from_addr,
        "bytecode": bytecode,
        "storage": {},
        "created_at": int(time.time())
    }
    
    return contract_addr

def call_contract(from_addr, contract_addr, method=None, args=None):
    """Вызов смарт-контракта"""
    if contract_addr not in state["contracts"]:
        return {"error": "Contract not found"}
    
    contract = state["contracts"][contract_addr]
    vm = MiniEVM()
    
    context = {
        "from": from_addr,
        "to": contract_addr,
        "storage": contract["storage"].copy(),
        "method": method,
        "args": args or {}
    }
    
    try:
        result = vm.execute_bytecode(contract["bytecode"], context)
        contract["storage"] = context["storage"]
        
        return {
            "success": True,
            "stack": result["stack"],
            "gas_used": result["gas_used"],
            "storage": contract["storage"]
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def deploy_token_contract(from_addr, name, symbol, supply):
    """Развернуть токен-контракт (шаблон)"""
    bytecode = f"""
    # Token Contract
    PUSH {supply}
    STORE totalSupply
    PUSH {supply}
    STORE balances_{from_addr}
    STOP
    """
    return deploy_contract(from_addr, bytecode)

if __name__ == "__main__":
    # Тест EVM
    print("=" * 60)
    print("🧠 MINI EVM TEST")
    print("=" * 60)
    
    vm = MiniEVM()
    
    # Тест 1: Арифметика
    print("\n[TEST 1] Arithmetic")
    code1 = """
    PUSH 5
    PUSH 7
    ADD
    """
    result = vm.execute_bytecode(code1)
    print(f"   5 + 7 = {result['stack'][-1] if result['stack'] else '?'}")
    
    # Тест 2: Storage
    print("\n[TEST 2] Storage")
    code2 = """
    PUSH 100
    STORE balance
    LOAD balance
    """
    result = vm.execute_bytecode(code2)
    print(f"   Stored 100, loaded: {result['stack'][-1] if result['stack'] else '?'}")
    
    # Тест 3: Деплой контракта
    print("\n[TEST 3] Deploy contract")
    addr = deploy_contract("0xowner", "PUSH 42 STOP")
    print(f"   Contract deployed at: {addr}")
    
    print("\n✅ EVM Engine ready!")
