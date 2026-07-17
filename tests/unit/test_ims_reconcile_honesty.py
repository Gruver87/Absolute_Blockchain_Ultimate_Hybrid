#!/usr/bin/env python3
"""IMS reconcile + address activity satoshi + tip-root soak contract."""

import inspect
import os
import tempfile

from blockchain.immutable_state import ImmutableStateManager
from crypto.native import _python_state_root_from_accounts
from runtime.amount import to_satoshi
from storage.database import Database


def test_ims_reconcile_from_store_mirrors_db():
    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "ims.db"))
    db.initialize()
    db.set_balance("alice", 12.5)
    db.set_balance("bob", 1)
    ims = ImmutableStateManager()
    ims.seed_from_balances({"alice": 999})  # stale shadow
    n = ims.reconcile_from_store(db, ["alice", "bob"])
    assert n == 2
    assert ims.get_balance_satoshi("alice") == to_satoshi(12.5)
    assert ims.get_balance_satoshi("bob") == to_satoshi(1)


def test_get_address_activity_includes_satoshi():
    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "act.db"))
    db.initialize()
    db.set_balance("0x" + "11" * 20, 4.25)
    act = db.get_address_activity("0x" + "11" * 20)
    assert act["balance_satoshi"] == to_satoshi(4.25)
    assert abs(act["balance"] - 4.25) < 1e-12


def test_tip_state_root_python_keeps_float_b_contract():
    src = inspect.getsource(_python_state_root_from_accounts)
    assert '"b"' in src
    assert "round(float" in src


def test_sqlite_total_supply_prefers_satoshi():
    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "sup.db"))
    db.initialize()
    db.set_balance("a", 1.5)
    db.set_balance("b", 2.5)
    assert abs(db.get_total_supply() - 4.0) < 1e-12
