#!/usr/bin/env python3
"""Production EVM deploy salt requirements."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from execution.evm_adapter import EVMAdapter
from runtime.config import Config
from storage.database import Database
import tempfile


def test_prod_deploy_requires_salt():
    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "salt.db"))
    db.initialize()
    cfg = Config(db_path=db.db_path)
    cfg.deployment_mode = "prod"
    cfg.evm_require_deploy_salt = True
    adapter = EVMAdapter(db, cfg)
    deployer = "0x" + "1" * 40
    db.set_balance(deployer, 10.0)
    res = adapter.deploy_contract(deployer, "600160005260206000f3")
    assert res.success is False
    assert res.error == "deploy_salt_required"


def test_prod_deploy_with_salt_ok():
    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "salt2.db"))
    db.initialize()
    cfg = Config(db_path=db.db_path)
    cfg.deployment_mode = "prod"
    cfg.evm_require_deploy_salt = True
    adapter = EVMAdapter(db, cfg)
    deployer = "0x" + "2" * 40
    db.set_balance(deployer, 10.0)
    res = adapter.deploy_contract(deployer, "600160005260206000f3", salt="prod-salt-1")
    assert res.success, res.error


def test_prod_deploy_eip1014_address():
    from crypto import native

    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "salt3.db"))
    db.initialize()
    cfg = Config(db_path=db.db_path)
    cfg.deployment_mode = "prod"
    cfg.evm_require_deploy_salt = True
    cfg.evm_create2_eip1014 = True
    adapter = EVMAdapter(db, cfg)
    deployer = "0x" + "3" * 40
    db.set_balance(deployer, 10.0)
    bytecode_hex = "600160005260206000f3"
    salt = "block:1:0xabc"
    bytecode = bytes.fromhex(bytecode_hex)
    expected = native.evm_create2_address_eip1014(
        deployer,
        adapter._deploy_salt_to_word(salt),
        bytecode,
    )
    res = adapter.deploy_contract(deployer, bytecode_hex, salt=salt, block_number=1)
    assert res.success, res.error
    assert res.return_value == expected
