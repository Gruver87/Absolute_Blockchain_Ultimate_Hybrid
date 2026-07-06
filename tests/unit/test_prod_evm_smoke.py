#!/usr/bin/env python3
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from prod_evm_smoke import DEPLOY_BYTECODE, _storage_ok


def test_deploy_bytecode_non_empty():
    assert len(DEPLOY_BYTECODE) >= 8


def test_storage_ok_accepts_slot_one():
    assert _storage_ok(
        "0x0000000000000000000000000000000000000000000000000000000000000001"
    )


def test_storage_ok_rejects_zero():
    assert not _storage_ok(
        "0x0000000000000000000000000000000000000000000000000000000000000000"
    )
