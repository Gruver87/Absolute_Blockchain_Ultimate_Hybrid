#!/usr/bin/env python3
"""Industrial gate: EVM opcode parity tests (native + interpreter)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EVM_OPCODE_TESTS = [
    "tests/unit/test_evm_extended_opcodes.py",
    "tests/unit/test_evm_cancun_opcodes.py",
    "tests/unit/test_evm_blob_opcodes.py",
    "tests/unit/test_evm_solidity_ops.py",
    "tests/unit/test_native_deploy_address.py",
]


def run_evm_opcode_parity_gate() -> int:
    cmd = [sys.executable, "-m", "pytest", *EVM_OPCODE_TESTS, "-q", "--tb=no"]
    proc = subprocess.run(cmd, cwd=str(ROOT))
    return int(proc.returncode)


def main() -> int:
    rc = run_evm_opcode_parity_gate()
    if rc == 0:
        print(f"OK: EVM opcode parity ({len(EVM_OPCODE_TESTS)} modules)")
    else:
        print(f"FAIL: EVM opcode parity gate exit {rc}", file=sys.stderr)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
