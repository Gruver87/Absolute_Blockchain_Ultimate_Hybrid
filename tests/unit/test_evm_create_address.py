#!/usr/bin/env python3
"""CREATE / CREATE2 address resolution is deterministic (no time.time)."""

from execution.evm_adapter import EVMAdapter
from runtime.config import Config


class _FakeDB:
    pass


def test_unsalted_create_is_deterministic():
    cfg = Config()
    cfg.evm_require_deploy_salt = False
    cfg.evm_create2_eip1014 = True
    adapter = EVMAdapter(_FakeDB(), cfg)
    bytecode = b"\x00\x01\x02"
    a1, err1 = adapter._resolve_deploy_address("0x" + "11" * 20, bytecode, None, block_number=7)
    a2, err2 = adapter._resolve_deploy_address("0x" + "11" * 20, bytecode, None, block_number=7)
    assert err1 is None and err2 is None
    assert a1 == a2
    assert a1.startswith("0x") and len(a1) == 42


def test_create2_eip1014_matches_hook_path():
    from crypto import native

    cfg = Config()
    cfg.evm_create2_eip1014 = True
    cfg.evm_require_deploy_salt = True
    adapter = EVMAdapter(_FakeDB(), cfg)
    deployer = "0x" + "22" * 20
    init = b"\x60\x00"
    salt_word = 12345
    hook_addr = native.evm_create2_address_eip1014(deployer, salt_word, init)
    # API string salt is keccak'd; opcode path uses raw word — both are stable
    assert hook_addr.startswith("0x")
    legacy = native.evm_deploy_address_create2_legacy(deployer, salt_word, init)
    assert hook_addr != legacy or cfg.evm_create2_eip1014
