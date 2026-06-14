#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EVM Adapter — подключает evm_interpreter.py к живому состоянию блокчейна.

Обеспечивает:
  - Деплой смарт-контрактов (сохранение байткода в БД)
  - Вызов методов контрактов (загрузка/сохранение storage из БД)
  - Оценка газа
"""

import hashlib
import json
import sys
import os
import time
from typing import Optional, Dict, Any

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from evm_interpreter import EVM, EVMContext
from storage.database import Database
from runtime.config import Config


class EVMResult:
    """Результат выполнения EVM-транзакции."""

    def __init__(self, success: bool, return_value: Any = None,
                 gas_used: int = 0, error: str = "", logs: list = None,
                 storage_changes: Dict = None):
        self.success = success
        self.return_value = return_value
        self.gas_used = gas_used
        self.error = error
        self.logs = logs or []
        self.storage_changes = storage_changes or {}

    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "return_value": self.return_value,
            "gas_used": self.gas_used,
            "error": self.error,
            "logs": self.logs,
            "storage_changes": self.storage_changes,
        }


class EVMAdapter:
    """
    Адаптер EVM: связывает evm_interpreter.EVM с хранилищем узла.
    Загружает/сохраняет storage и bytecode в Database.
    """

    def __init__(self, db: Database, config: Config):
        self.db = db
        self.config = config

    def _make_context(self, caller: str, contract_addr: str = "",
                      calldata: bytes = b"", value: int = 0) -> EVMContext:
        tip = self.db.get_chain_tip() if hasattr(self.db, "get_chain_tip") else 0
        last = self.db.get_last_block() if hasattr(self.db, "get_last_block") else None
        ts = int(last.get("timestamp", 0)) if last else int(time.time())
        return EVMContext(
            caller=caller or "",
            origin=caller or "",
            address=contract_addr or "",
            calldata=calldata or b"",
            value=int(value),
            block_number=int(tip),
            timestamp=ts,
            chain_id=int(getattr(self.config, "chain_id", 77777)),
            balance_of=lambda addr: int(self.db.get_balance(addr) * 10**18),
        )

    def _normalize_addr(self, word_or_addr: str) -> str:
        raw = str(word_or_addr).replace("0x", "").lower()
        if len(raw) <= 40 and all(c in "0123456789abcdef" for c in raw):
            return "0x" + raw.rjust(40, "0")[-40:]
        return word_or_addr

    def _contract_call_hook(self, target: str, calldata: bytes, value: int,
                            gas: int, delegate: bool, static: bool,
                            caller_ctx: EVMContext) -> Dict[str, Any]:
        target = self._normalize_addr(target)
        account = self.db.get_account(target)
        if not account or not account.get("code"):
            return {"success": False, "reverted": True, "return_data": b""}
        try:
            bytecode = bytes.fromhex(account["code"].replace("0x", ""))
        except ValueError:
            return {"success": False, "reverted": True, "return_data": b""}

        if delegate:
            storage_raw = self.db.get_account(caller_ctx.address)
            storage_src = (storage_raw or {}).get("storage") or "{}"
            exec_addr = caller_ctx.address
            call_value = 0
            caller = caller_ctx.caller
        else:
            storage_src = account.get("storage") or "{}"
            exec_addr = target
            call_value = value
            caller = caller_ctx.address

        try:
            storage = {int(k): int(v) for k, v in json.loads(storage_src).items()}
        except Exception:
            storage = {}

        sub_ctx = self._make_context(caller, exec_addr, calldata, call_value)
        sub_ctx.contract_call = lambda t, d, v, g, delg, st: self._contract_call_hook(
            t, d, v, g, delg, st, sub_ctx
        )
        sub_ctx.contract_create = lambda code, val, ctx, salt=None: self._contract_create_hook(
            code, val, ctx, salt
        )
        evm = EVM(gas_limit=gas or self.config.evm_gas_limit, context=sub_ctx)
        evm.storage = dict(storage)
        result = evm.execute_bytecode(bytecode)

        if static:
            return {
                "success": not result.get("reverted"),
                "reverted": result.get("reverted", False),
                "return_data": result.get("return_data", b"") or b"",
                "gas_used": result.get("gas_used", 0),
            }

        if delegate:
            new_storage = {str(k): v for k, v in result.get("storage", {}).items()}
            self.db.update_account_storage(caller_ctx.address, new_storage)
        else:
            if not result.get("reverted"):
                new_storage = {str(k): v for k, v in result.get("storage", {}).items()}
                self.db.update_account_storage(target, new_storage)
                if call_value > 0:
                    wei_to_abs = call_value / 10**18
                    self.db.update_balance(caller, -wei_to_abs)
                    self.db.update_balance(target, wei_to_abs)

        return {
            "success": not result.get("reverted"),
            "reverted": result.get("reverted", False),
            "return_data": result.get("return_data", b"") or b"",
            "storage": result.get("storage", {}),
            "gas_used": result.get("gas_used", 0),
        }

    def _contract_create_hook(self, init_code: bytes, value: int,
                              caller_ctx: EVMContext,
                              salt: Optional[int] = None) -> Dict[str, Any]:
        deployer = caller_ctx.address or caller_ctx.caller
        if not deployer:
            return {"success": False, "reverted": True, "gas_used": 0}
        if salt is not None:
            seed = f"create2:{deployer}:{salt}:{init_code.hex()}"
        else:
            seed = f"{deployer}{caller_ctx.block_number}{len(init_code)}"
        contract_addr = "0x" + hashlib.sha256(seed.encode()).hexdigest()[:40]
        try:
            result = self._run_evm(
                init_code, {}, self.config.evm_gas_limit,
                caller=deployer,
                contract_addr=contract_addr,
                value=value,
            )
        except Exception:
            return {"success": False, "reverted": True, "gas_used": 0}

        if result.get("reverted"):
            return {
                "success": False,
                "reverted": True,
                "gas_used": result.get("gas_used", 0),
            }

        ret_code = result.get("return_data") or b""
        code_hex = ret_code.hex() if ret_code else init_code.hex()
        self.db.save_account(
            address=contract_addr,
            balance=value / 10**18 if value else 0.0,
            nonce=0,
            code=code_hex,
            storage=json.dumps(
                {str(k): v for k, v in result.get("storage", {}).items()}
            ),
        )
        if value > 0:
            wei_to_abs = value / 10**18
            self.db.update_balance(deployer, -wei_to_abs)
            self.db.update_balance(contract_addr, wei_to_abs)

        return {
            "success": True,
            "reverted": False,
            "address": contract_addr,
            "gas_used": result.get("gas_used", 0),
        }

    def _run_evm(self, bytecode: bytes, storage: Dict[int, int], gas_limit: int,
                 caller: str = "", contract_addr: str = "",
                 calldata: bytes = b"", value: int = 0) -> Dict:
        ctx = self._make_context(caller, contract_addr, calldata, value)
        ctx.contract_call = lambda t, d, v, g, delg, st: self._contract_call_hook(
            t, d, v, g, delg, st, ctx
        )
        ctx.contract_create = lambda code, val, c, salt=None: self._contract_create_hook(
            code, val, c, salt
        )
        evm = EVM(gas_limit=gas_limit, context=ctx)
        evm.storage = dict(storage)
        return evm.execute_bytecode(bytecode)

    def deploy_contract(self, deployer: str, bytecode_hex: str,
                        value: float = 0.0, gas_limit: int = 0,
                        salt: str = None) -> EVMResult:
        """
        Деплоит смарт-контракт.
        Сохраняет байткод и начальное состояние в БД.
        Возвращает адрес контракта.
        """
        gas_limit = gas_limit or self.config.evm_gas_limit

        try:
            bytecode = bytes.fromhex(bytecode_hex.replace("0x", ""))
        except ValueError as e:
            return EVMResult(success=False, error=f"invalid_bytecode: {e}")

        if not bytecode:
            return EVMResult(success=False, error="empty_bytecode")

        # Deterministic address when salt provided (block execution); else dev-only
        seed = salt if salt is not None else str(time.time())
        contract_addr = "0x" + hashlib.sha256(
            f"{deployer}{seed}".encode()
        ).hexdigest()[:40]

        # Выполняем конструктор
        try:
            result = self._run_evm(
                bytecode, {}, gas_limit,
                caller=deployer,
                contract_addr=contract_addr,
                value=int(value * 10**18) if value else 0,
            )
        except Exception as e:
            return EVMResult(success=False, error=str(e))

        if result.get("reverted"):
            return EVMResult(success=False, error="constructor_reverted",
                             gas_used=result["gas_used"])

        # Сохраняем контракт в БД
        self.db.save_account(
            address=contract_addr,
            balance=value,
            nonce=0,
            code=bytecode_hex,
            storage=json.dumps(result.get("storage", {})),
        )

        # Стоимость деплоя списывается с deployer
        if value > 0:
            self.db.update_balance(deployer, -value)
            self.db.update_balance(contract_addr, value)

        return EVMResult(
            success=True,
            return_value=contract_addr,
            gas_used=result["gas_used"],
            storage_changes=result.get("storage", {}),
        )

    # ── Вызов контракта ──────────────────────────────────────────────────────

    def call_contract(self, caller: str, contract_addr: str,
                      calldata_hex: str = "", value: float = 0.0,
                      gas_limit: int = 0) -> EVMResult:
        """
        Вызывает метод смарт-контракта (изменяет состояние).
        Загружает bytecode и storage из БД, после выполнения сохраняет изменения.
        """
        gas_limit = gas_limit or self.config.evm_gas_limit

        account = self.db.get_account(contract_addr)
        if not account or not account.get("code"):
            return EVMResult(success=False, error="not_a_contract")

        try:
            bytecode = bytes.fromhex(account["code"].replace("0x", ""))
        except ValueError as e:
            return EVMResult(success=False, error=f"invalid_stored_bytecode: {e}")

        # Загружаем хранилище контракта
        storage_raw = account.get("storage") or "{}"
        try:
            storage = {int(k): int(v) for k, v in json.loads(storage_raw).items()}
        except Exception:
            storage = {}

        try:
            calldata = bytes.fromhex(calldata_hex.replace("0x", "")) if calldata_hex else b""
        except ValueError:
            calldata = b""

        try:
            result = self._run_evm(
                bytecode, storage, gas_limit,
                caller=caller,
                contract_addr=contract_addr,
                calldata=calldata,
                value=int(value * 10**18) if value else 0,
            )
        except Exception as e:
            return EVMResult(success=False, error=str(e))

        if result.get("reverted"):
            return EVMResult(success=False, error="execution_reverted",
                             gas_used=result["gas_used"])

        # Сохраняем изменённое storage
        new_storage = {str(k): v for k, v in result.get("storage", {}).items()}
        self.db.update_account_storage(contract_addr, new_storage)

        # Перевод value от caller к контракту
        if value > 0:
            self.db.update_balance(caller, -value)
            self.db.update_balance(contract_addr, value)

        # Возвращаемое значение — return_data или стек
        ret = result.get("return_data") or b""
        if ret:
            return_value = int.from_bytes(ret[:32].ljust(32, b"\x00"), "big")
        else:
            stack = result.get("stack", [])
            return_value = stack[-1] if stack else None

        return EVMResult(
            success=not result.get("reverted", False),
            return_value=return_value,
            gas_used=result["gas_used"],
            storage_changes=new_storage,
        )

    # ── Статический вызов (read-only) ────────────────────────────────────────

    def static_call(self, contract_addr: str,
                    calldata_hex: str = "", gas_limit: int = 0) -> EVMResult:
        """
        Вызывает контракт без изменения состояния (eth_call).
        Storage НЕ сохраняется.
        """
        gas_limit = gas_limit or self.config.evm_gas_limit

        account = self.db.get_account(contract_addr)
        if not account or not account.get("code"):
            return EVMResult(success=False, error="not_a_contract")

        try:
            bytecode = bytes.fromhex(account["code"].replace("0x", ""))
        except ValueError as e:
            return EVMResult(success=False, error=f"invalid_bytecode: {e}")

        storage_raw = account.get("storage") or "{}"
        try:
            storage = {int(k): int(v) for k, v in json.loads(storage_raw).items()}
        except Exception:
            storage = {}

        try:
            calldata = bytes.fromhex(calldata_hex.replace("0x", "")) if calldata_hex else b""
        except ValueError:
            calldata = b""

        try:
            result = self._run_evm(
                bytecode, storage, gas_limit,
                caller="",
                contract_addr=contract_addr,
                calldata=calldata,
            )
        except Exception as e:
            return EVMResult(success=False, error=str(e), gas_used=0)

        ret = result.get("return_data") or b""
        if ret:
            return_value = int.from_bytes(ret[:32].ljust(32, b"\x00"), "big")
        else:
            stack = result.get("stack", [])
            return_value = stack[-1] if stack else None

        return EVMResult(
            success=not result.get("reverted", False),
            return_value=return_value,
            gas_used=result["gas_used"],
        )

    # ── Оценка газа ──────────────────────────────────────────────────────────

    def estimate_gas(self, contract_addr: str, calldata_hex: str = "") -> int:
        """Оценивает количество газа для вызова. Запускает dry-run."""
        result = self.static_call(contract_addr, calldata_hex,
                                  gas_limit=self.config.evm_gas_limit)
        if result.success:
            return int(result.gas_used * 1.2)  # +20% буфер
        return self.config.evm_gas_limit

    # ── Справочная информация ────────────────────────────────────────────────

    def get_contract_info(self, contract_addr: str) -> Dict:
        """Возвращает информацию о смарт-контракте."""
        account = self.db.get_account(contract_addr)
        if not account:
            return {"exists": False}
        return {
            "exists": True,
            "address": contract_addr,
            "is_contract": bool(account.get("code")),
            "balance": account.get("balance", 0.0),
            "code_size": len(account.get("code") or "") // 2,
            "storage_slots": len(json.loads(account.get("storage") or "{}")),
        }
