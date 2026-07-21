#!/usr/bin/env python3
"""v1.3.45: native apply writeback / receipt status honesty."""

from __future__ import annotations

import json
import os
import tempfile

from core.blockchain import Blockchain, Transaction
from runtime.config import Config
from storage.database import Database


def test_writeback_skips_empty_new_accounts_and_preserves_code():
    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "w.db"))
    db.initialize()
    cfg = Config()
    bc = Blockchain(cfg, db)

    existing = "0x" + "ab" * 20
    db.save_account(existing, balance=1.0, nonce=0, code="6000", storage='{"0":1}')
    burn = "0x000000000000000000000000000000000000dead"

    bc._writeback_accounts_sat(
        {
            existing: {"balance": 2_000_000, "nonce": 1},
            burn: {"balance": 0, "nonce": 0},
        }
    )

    assert db.get_account(burn) is None
    row = db.get_account(existing)
    assert row is not None
    assert row.get("code") == "6000"
    assert json.loads(row.get("storage") or "{}").get("0") == 1
    assert int(row.get("nonce") or 0) == 1


def test_simple_transfer_receipt_status_one():
    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "r.db"))
    db.initialize()
    cfg = Config()
    cfg.miner_address = "0x" + "1" * 40
    cfg.burn_address = "0x" + "d" * 40
    db.update_balance(cfg.miner_address, 10_000.0)
    bc = Blockchain(cfg, db)
    tx = Transaction(
        from_addr=cfg.miner_address,
        to_addr="0x" + "2" * 40,
        value=1.0,
        nonce=0,
    )
    block = bc.create_block([tx], cfg.miner_address)
    assert bc.add_block(block) is True
    rcpt = db.get_tx_receipt(tx.hash)
    assert rcpt is not None
    assert rcpt["status"] == 1


def test_example_manifest_has_no_zero_prefix_placeholders():
    from runtime.mainnet_constants import is_zero_prefix_placeholder_address
    from runtime.validator_loader import load_manifest, manifest_entries

    manifest = load_manifest("validators.manifest.example.json")
    addrs = [str(r.get("address", "")) for r in manifest_entries(manifest)]
    assert len(addrs) >= 3
    assert not any(is_zero_prefix_placeholder_address(a) for a in addrs)
