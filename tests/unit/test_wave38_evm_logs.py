"""Wave 38 — BLOCKHASH, CALLCODE, persisted EVM logs."""
import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)


def test_blockhash_and_callcode_supported():
    from execution.evm_bytecode_validator import validate_bytecode_hex
    assert validate_bytecode_hex("0x4000")["valid"] is True
    assert validate_bytecode_hex("0xf200")["valid"] is True


def test_blockhash_returns_zero_for_future_block():
    from execution.evm_adapter import EVMAdapter
    from runtime.config import Config
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "bh.db"))
    db.initialize()
    cfg = Config(db_path=db.db_path)
    adapter = EVMAdapter(db, cfg)
    assert adapter._block_hash_word(999_999) == 0


def test_evm_logs_persisted_on_deploy():
    from execution.evm_adapter import EVMAdapter
    from runtime.config import Config
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "log.db"))
    db.initialize()
    cfg = Config(db_path=db.db_path)
    adapter = EVMAdapter(db, cfg)
    deployer = "0x" + "2" * 40
    db.set_balance(deployer, 50.0)

    # PUSH0 PUSH0 LOG0 STOP
    res = adapter.deploy_contract(deployer, "5f5fa000", salt="w38-log")
    assert res.success, res.error

    logs = db.get_evm_logs(contract_address=res.return_value, limit=10)
    assert len(logs) >= 1
    assert logs[0]["contract_address"] == res.return_value


def test_get_evm_logs_all():
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "all.db"))
    db.initialize()
    db.save_evm_logs(
        "0x" + "3" * 40,
        [{"topics": ["0x01"], "data": "dead"}],
        block_height=1,
    )
    rows = db.get_evm_logs(limit=5)
    assert len(rows) == 1
    assert rows[0]["data"] == "dead"
