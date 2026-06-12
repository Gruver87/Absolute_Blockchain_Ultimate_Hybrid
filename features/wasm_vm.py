"""WASM VM — WebAssembly-style smart contract execution environment."""

import hashlib
import json
import time
from typing import Dict, List, Optional, Any


class WASMContract:
    def __init__(self, address: str, code: str, owner: str, name: str):
        self.address = address
        self.code = code
        self.owner = owner
        self.name = name
        self.created_at = int(time.time())
        self.abi = {
            "functions": ["constructor", "balanceOf", "transfer", "getInfo", "getOwner"]
        }
        self.call_count = 0

    def to_dict(self) -> Dict:
        return {
            "address": self.address,
            "name": self.name,
            "owner": self.owner[:16] + "...",
            "created_at": self.created_at,
            "call_count": self.call_count,
            "abi": self.abi,
            "code_size": len(self.code),
        }


class WASMVirtualMachine:
    """
    WebAssembly-style VM for executing smart contracts.
    Supports deploy, call, and storage inspection.
    """

    GAS_LIMIT = 10_000_000

    def __init__(self):
        self.contracts: Dict[str, WASMContract] = {}
        self.storage: Dict[str, Dict] = {}   # contract_addr -> key -> value
        self.events: List[Dict] = []
        print("[WASM VM] Initialized")

    def deploy(self, code: str, owner: str, name: str = None,
               init_params: Dict = None) -> str:
        contract_addr = "wasm_" + hashlib.sha256(
            f"{code}{owner}{time.time()}".encode()
        ).hexdigest()[:40]
        name = name or f"Contract_{contract_addr[:8]}"
        contract = WASMContract(contract_addr, code, owner, name)
        self.contracts[contract_addr] = contract
        self.storage[contract_addr] = {}
        # Auto-run constructor
        if init_params:
            self._run_constructor(contract_addr, init_params, owner)
        self._log_event({
            "type": "ContractDeployed",
            "address": contract_addr,
            "owner": owner,
            "name": name,
            "timestamp": int(time.time()),
        })
        print(f"[WASM VM] Deployed: {contract_addr[:20]}... name={name}")
        return contract_addr

    def call(self, contract_addr: str, function_name: str,
             params: Dict, caller: str, value: float = 0.0) -> Dict:
        contract = self.contracts.get(contract_addr)
        if not contract:
            return {"success": False, "error": "Contract not found", "gas_used": 0}
        gas_used = 5000 + len(function_name) * 100 + len(json.dumps(params)) * 50
        if gas_used > self.GAS_LIMIT:
            return {"success": False, "error": "Out of gas", "gas_used": gas_used}
        result = self._execute(contract, function_name, params, caller, value)
        contract.call_count += 1
        self._log_event({
            "type": "FunctionCall",
            "contract": contract_addr[:16] + "...",
            "function": function_name,
            "caller": caller[:16] + "...",
            "gas_used": gas_used,
            "timestamp": int(time.time()),
        })
        return {
            "success": result.get("success", True),
            "result": result.get("result"),
            "gas_used": gas_used,
            "data": result.get("data"),
        }

    def get_contract(self, addr: str) -> Optional[Dict]:
        c = self.contracts.get(addr)
        return c.to_dict() if c else None

    def get_all_contracts(self) -> List[Dict]:
        return [c.to_dict() for c in self.contracts.values()]

    def get_storage(self, addr: str) -> Dict:
        return dict(self.storage.get(addr, {}))

    def get_events(self, limit: int = 100) -> List[Dict]:
        return self.events[-limit:][::-1]

    def get_stats(self) -> Dict:
        return {
            "contracts_count": len(self.contracts),
            "total_calls": sum(c.call_count for c in self.contracts.values()),
            "storage_keys": sum(len(s) for s in self.storage.values()),
            "events_count": len(self.events),
            "gas_limit": self.GAS_LIMIT,
        }

    # ── Internal execution helpers ──────────────────────────────────────────

    def _run_constructor(self, addr: str, params: Dict, owner: str):
        initial_supply = params.get("initialSupply", 1_000_000)
        if addr not in self.storage:
            self.storage[addr] = {}
        self.storage[addr][f"balance_{owner}"] = initial_supply
        self.storage[addr]["totalSupply"] = initial_supply

    def _execute(self, contract: WASMContract, fn: str,
                 params: Dict, caller: str, value: float) -> Dict:
        addr = contract.address
        store = self.storage.get(addr, {})
        if fn == "balanceOf":
            account = params.get("account", caller)
            return {"success": True, "result": store.get(f"balance_{account}", 0)}
        elif fn == "transfer":
            to = params.get("to")
            amount = params.get("amount", 0)
            if not to:
                return {"success": False, "error": "Recipient required"}
            if amount <= 0:
                return {"success": False, "error": "Amount must be > 0"}
            from_bal = store.get(f"balance_{caller}", 0)
            if from_bal < amount:
                return {"success": False, "error": "Insufficient balance"}
            store[f"balance_{caller}"] = from_bal - amount
            store[f"balance_{to}"] = store.get(f"balance_{to}", 0) + amount
            self.storage[addr] = store
            return {"success": True, "result": True}
        elif fn == "constructor":
            self._run_constructor(addr, params, caller)
            return {"success": True, "result": "Initialized"}
        elif fn == "getInfo":
            return {"success": True, "result": contract.name}
        elif fn == "getOwner":
            return {"success": True, "result": contract.owner}
        elif fn == "totalSupply":
            return {"success": True, "result": store.get("totalSupply", 0)}
        elif fn == "setStorage":
            key = params.get("key")
            val = params.get("value")
            if key:
                store[key] = val
                self.storage[addr] = store
                return {"success": True, "result": True}
            return {"success": False, "error": "Key required"}
        elif fn == "getStorage":
            key = params.get("key")
            return {"success": True, "result": store.get(key) if key else None}
        else:
            code = contract.code
            if f"fn {fn}" in code or f"function {fn}" in code or f"def {fn}" in code:
                return {"success": True, "result": f"Function {fn} executed (custom)"}
            return {"success": False, "error": f"Function '{fn}' not found"}

    def _log_event(self, event: Dict):
        self.events.append(event)
        if len(self.events) > 10_000:
            self.events = self.events[-10_000:]
