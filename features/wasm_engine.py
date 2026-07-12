"""WebAssembly execution engine — wasmtime with host storage ABI."""

from __future__ import annotations

import base64
from typing import Any, Dict, List, Optional

try:
    import wasmtime

    HAS_WASMTIME = True
except ImportError:
    wasmtime = None
    HAS_WASMTIME = False


class WASMEngine:
    """Execute WASM bytecode via wasmtime; host imports for contract storage."""

    def __init__(self, storage: Dict[str, Any], gas_limit: int = 10_000_000):
        self.storage = storage
        self.gas_limit = gas_limit
        self.gas_used = 0
        self.logs: List[str] = []

    @staticmethod
    def available() -> bool:
        return HAS_WASMTIME

    def _charge(self, units: int) -> bool:
        self.gas_used += units
        return self.gas_used <= self.gas_limit

    def execute(
        self,
        wasm_bytes: bytes,
        export_name: str,
        params: Dict[str, Any],
        caller: str,
    ) -> Dict[str, Any]:
        if not HAS_WASMTIME:
            return {
                "success": False,
                "error": "wasmtime not installed (pip install wasmtime)",
                "gas_used": 0,
            }
        self.gas_used = 0
        self.logs.clear()
        engine = wasmtime.Engine()
        store = wasmtime.Store(engine)
        host = self

        def storage_get(caller, key_ptr: int, key_len: int, out_ptr: int, out_max: int) -> int:
            if not host._charge(500):
                return -1
            mem = caller.get("memory")
            if mem is None:
                return -1
            data = mem.read(store, key_ptr, key_len)
            key = bytes(data).decode("utf-8", errors="replace")
            val = str(host.storage.get(key, "")).encode("utf-8")[:out_max]
            mem.write(store, out_ptr, val)
            return len(val)

        def storage_set(caller, key_ptr: int, key_len: int, val_ptr: int, val_len: int) -> int:
            if not host._charge(800):
                return -1
            mem = caller.get("memory")
            if mem is None:
                return -1
            key = bytes(mem.read(store, key_ptr, key_len)).decode("utf-8", errors="replace")
            val = bytes(mem.read(store, val_ptr, val_len)).decode("utf-8", errors="replace")
            host.storage[key] = val
            return 0

        linker = wasmtime.Linker(engine)
        linker.define(
            store,
            "env",
            "storage_get",
            wasmtime.Func(
                store,
                wasmtime.FuncType(
                    [wasmtime.ValType.i32()] * 4,
                    [wasmtime.ValType.i32()],
                ),
                storage_get,
            ),
        )
        linker.define(
            store,
            "env",
            "storage_set",
            wasmtime.Func(
                store,
                wasmtime.FuncType(
                    [wasmtime.ValType.i32()] * 4,
                    [wasmtime.ValType.i32()],
                ),
                storage_set,
            ),
        )
        module = wasmtime.Module(engine, wasm_bytes)
        instance = linker.instantiate(store, module)
        exports = instance.exports(store)
        func = exports.get(export_name)
        if func is None:
            return {
                "success": False,
                "error": f"export '{export_name}' not found",
                "gas_used": self.gas_used,
            }
        if not self._charge(2000):
            return {"success": False, "error": "Out of gas", "gas_used": self.gas_used}
        args = []
        if "a" in params and "b" in params:
            args = [int(params["a"]), int(params["b"])]
        elif "x" in params:
            args = [int(params["x"])]
        try:
            result = func(store, *args) if args else func(store)
        except Exception as exc:
            return {"success": False, "error": str(exc), "gas_used": self.gas_used}
        return {
            "success": True,
            "result": result,
            "gas_used": self.gas_used,
            "logs": list(self.logs),
            "engine": "wasmtime",
            "caller": caller,
        }

    @staticmethod
    def decode_module(code: str) -> bytes:
        raw = code.strip()
        if raw.startswith("(module"):
            raise ValueError("WAT text modules require wat2wasm; pass WASM binary base64")
        try:
            return base64.b64decode(raw, validate=True)
        except Exception:
            return raw.encode("utf-8")
