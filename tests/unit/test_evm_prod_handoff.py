#!/usr/bin/env python3
"""Prod fail-closed behavior for native EVM handoff."""

import pytest

from evm_interpreter import EVM


def test_handoff_raises_when_native_required(monkeypatch):
    monkeypatch.setenv("ABS_REQUIRE_NATIVE_CRYPTO", "true")
    # DIFFICULTY (0x44) is not implemented — forces native handoff
    bytecode = bytes([0x44, 0x00])
    with pytest.raises(RuntimeError, match="native EVM handoff"):
        EVM().execute_bytecode(bytecode)


def test_handoff_allowed_in_dev(monkeypatch):
    monkeypatch.delenv("ABS_REQUIRE_NATIVE_CRYPTO", raising=False)
    bytecode = bytes([0x44, 0x00])
    with pytest.raises(RuntimeError, match="unsupported opcode"):
        EVM().execute_bytecode(bytecode)
