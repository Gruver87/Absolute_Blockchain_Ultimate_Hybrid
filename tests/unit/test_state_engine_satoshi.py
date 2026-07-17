#!/usr/bin/env python3
"""StateEngine satoshi ledger + state_truth helpers."""

from execution.state_engine import StateEngine
from runtime.amount import SATOSHI_MULTIPLIER, to_satoshi
from runtime.state_truth import canonical_balance_abs, canonical_balance_satoshi


def test_state_engine_stores_satoshi_internally():
    eng = StateEngine()
    eng.create_genesis({"alice": 10, "bob": 0})
    assert eng.get_balance_satoshi("alice") == 10 * SATOSHI_MULTIPLIER
    assert eng.get_balance("alice") == 10  # whole ABS floor


def test_state_engine_transfer_and_fee_burn():
    eng = StateEngine()
    eng.create_genesis({"alice": 100, "bob": 0})
    eng.transition(
        {
            "number": 1,
            "hash": "h1",
            "parent_hash": "g",
            "timestamp": 1,
            "transactions": [
                {"from": "alice", "to": "bob", "amount": 10, "fee": 1, "nonce": 0}
            ],
        }
    )
    assert eng.get_balance("bob") == 10
    assert eng.get_balance("alice") == 89  # 100 - 10 - 1 fee burned
    assert eng.get_balance_satoshi("alice") == to_satoshi(89)


def test_canonical_balance_from_sqlite(tmp_path):
    from storage.database import Database

    db = Database(str(tmp_path / "t.db"))
    db.initialize()
    db.set_balance("0x" + "cd" * 20, 3.5)
    assert canonical_balance_satoshi(db, "0x" + "cd" * 20) == to_satoshi(3.5)
    assert abs(canonical_balance_abs(db, "0x" + "cd" * 20) - 3.5) < 1e-12
