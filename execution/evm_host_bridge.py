#!/usr/bin/env python3
"""Python host bridge for native EVM pure runner (state lookups)."""

from typing import Any, Optional


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


def make_evm_host_bridge(ctx: Optional[Any]) -> Optional[EvmHostBridge]:
    if ctx is None:
        return None
    return EvmHostBridge(ctx)
