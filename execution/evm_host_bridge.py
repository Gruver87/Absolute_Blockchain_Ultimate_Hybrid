#!/usr/bin/env python3
"""Python host bridge for native EVM pure runner (state lookups + runtime ops)."""

from typing import Any, Dict, List, Optional

from crypto import native


class EvmHostBridge:
    """Thin adapter from EVMContext callables to Rust host-bridge methods."""

    def __init__(self, ctx: Any):
        self._ctx = ctx

    def balance(self, addr: str) -> int:
        if self._ctx.balance_of:
            return int(self._ctx.balance_of(str(addr)))
        return 0

    def code_size(self, addr: str) -> int:
        if self._ctx.code_size_of:
            return int(self._ctx.code_size_of(str(addr)))
        return 0

    def code_copy(self, addr: str, offset: int, size: int) -> bytes:
        if self._ctx.code_copy_of:
            chunk = self._ctx.code_copy_of(str(addr), int(offset), int(size))
            return bytes(chunk or b"")
        return b""

    def block_hash(self, block_num: int) -> int:
        if self._ctx.block_hash_of:
            return int(self._ctx.block_hash_of(int(block_num)))
        return 0


class EvmRuntimeBridge(EvmHostBridge):
    """Full runtime bridge: syncs live EVM state for CALL/CREATE/LOG/SELFDESTRUCT."""

    def __init__(self, evm: Any):
        super().__init__(evm.ctx)
        self._evm = evm

    def _sync_in(
        self,
        stack: List[int],
        memory: bytearray,
        gas_used: int,
        storage: dict,
        return_data: bytes,
    ) -> None:
        self._evm.stack = [int(x) for x in stack]
        self._evm.memory = bytearray(memory)
        self._evm.gas_used = int(gas_used)
        if storage is self._evm.storage:
            pass
        else:
            self._evm.storage.clear()
            self._evm.storage.update(storage)
        self._evm.return_data = bytes(return_data)

    def _export_state(self) -> Dict[str, Any]:
        return {
            "stack": [int(x) for x in self._evm.stack],
            "memory": bytearray(self._evm.memory),
            "gas_used": int(self._evm.gas_used),
            "storage": dict(self._evm.storage),
            "return_data": bytes(self._evm.return_data),
            "running": bool(self._evm.running),
            "reverted": bool(self._evm.reverted),
            "logs": list(self._evm.logs),
        }

    def apply_host_op(
        self,
        op: int,
        stack: List[int],
        memory: bytearray,
        gas_limit: int,
        gas_used: int,
        storage: dict,
        return_data: bytes,
    ) -> Dict[str, Any]:
        op = int(op) & 0xFF
        self._sync_in(stack, memory, gas_used, storage, return_data)
        evm = self._evm
        evm.gas_limit = int(gas_limit)

        if 0xA0 <= op <= 0xA4:
            n_topics = op - 0xA0
            topics = [evm._pop() for _ in range(n_topics)]
            topics.reverse()
            size = evm._pop()
            offset = evm._pop()
            evm._consume_gas("LOG", extra=n_topics * 375 + int(size))
            evm._mem_extend(offset, size)
            data = native.evm_memory_slice(bytes(evm.memory), offset, size)
            if evm.ctx.emit_log:
                evm.ctx.emit_log(n_topics, topics, data)
            evm.logs.append({
                "topics": [hex(t) for t in topics],
                "data": data.hex(),
            })
        elif op == 0xF0:
            size = evm._pop()
            offset = evm._pop()
            value = evm._pop()
            evm._push(evm._execute_create(value, offset, size))
        elif op == 0xF5:
            salt = evm._pop()
            size = evm._pop()
            offset = evm._pop()
            value = evm._pop()
            evm._push(evm._execute_create(value, offset, size, salt))
        elif op in (0xF1, 0xF2, 0xF4, 0xFA):
            gas = evm._pop()
            to_word = evm._pop()
            value = evm._pop() if op not in (0xF4, 0xFA) else 0
            args_offset = evm._pop()
            args_size = evm._pop()
            ret_offset = evm._pop()
            ret_size = evm._pop()
            delegate = op == 0xF4
            static = op == 0xFA
            callcode = op == 0xF2
            evm._push(evm._execute_call(
                to_word, value, args_offset, args_size, ret_offset, ret_size,
                gas, delegate, static, callcode,
            ))
        elif op == 0xFF:
            beneficiary = evm._pop()
            if evm.ctx.selfdestruct:
                evm.ctx.selfdestruct(evm._word_to_addr(beneficiary))
            evm.running = False
        else:
            raise RuntimeError(f"unsupported host opcode 0x{op:02x}")

        return self._export_state()


def make_evm_host_bridge(ctx: Optional[Any]) -> Optional[EvmHostBridge]:
    if ctx is None:
        return None
    return EvmHostBridge(ctx)


def make_evm_runtime_bridge(evm: Optional[Any]) -> Optional[EvmRuntimeBridge]:
    if evm is None:
        return None
    return EvmRuntimeBridge(evm)
