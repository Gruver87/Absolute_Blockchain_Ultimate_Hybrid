#!/usr/bin/env python3
"""RocksDB native prefix scan for canonical state root."""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

from runtime.tokenomics import genesis_balances
from storage import keycodec as kc
from storage.rocks_store import RocksChainStore
from execution.state_root import compute_db_state_root


@pytest.fixture
def store(tmp_path):
    try:
        import abs_native  # noqa: F401
    except ImportError:
        pytest.skip("abs_native not built")
    if not hasattr(__import__("abs_native"), "RocksEngine"):
        pytest.skip("RocksEngine missing")
    engine_mod = __import__("abs_native")
    if not hasattr(engine_mod.RocksEngine, "state_root_from_account_prefix"):
        pytest.skip("state_root_from_account_prefix not in wheel")
    path = str(tmp_path / "chainstore")
    rs = RocksChainStore(path, synchronous="FULL")
    rs.initialize()
    yield rs
    rs.close()


def test_state_root_from_account_prefix_matches_db_kernel(store):
    founder = "0x" + "f" * 40
    for addr, amount in genesis_balances(founder).items():
        store.set_balance(addr, float(amount))
    store.update_balance("0x" + "1" * 40, 3.5)
    store.update_balance("0x" + "2" * 40, 7.25)

    via_prefix = store._engine.state_root_from_account_prefix(kc.prefix_accounts(), 100_000)
    via_store = store.compute_state_root()
    accounts = store.get_all_accounts()
    via_kernel = compute_db_state_root(accounts)

    assert via_prefix == via_kernel
    assert via_store == via_kernel
