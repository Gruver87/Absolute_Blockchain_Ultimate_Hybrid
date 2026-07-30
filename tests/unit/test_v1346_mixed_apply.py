#!/usr/bin/env python3
"""v1.3.46: mixed simple+EVM native apply path."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crypto import native
from core.blockchain import Blockchain, Transaction
from execution.evm_adapter import EVMAdapter
from kernel.event_bus import EventBus
from runtime.config import Config
from storage.database import Database


def test_wiring_mixed_helpers():
    text = Path("core/blockchain.py").read_text(encoding="utf-8")
    state = Path("core/components/state_service.py").read_text(encoding="utf-8")
    assert (
        "_block_transactions_are_mixed" in text
        or "_block_transactions_are_mixed" in state
    )
    assert "_apply_mixed_block_native" in text or "_apply_mixed_block_native" in state
    assert (
        "native mixed apply fallback" in text or "native mixed apply fallback" in state
    )
    assert hasattr(native, "blockchain_apply_host_effects")


def test_mixed_classifier():
    cfg = Config()
    db = Database(os.path.join(tempfile.mkdtemp(), "c.db"))
    db.initialize()
    bc = Blockchain(cfg, db, EventBus())
    bc.evm = EVMAdapter(db, cfg)
    simple = Transaction(from_addr="0xa", to_addr="0xb", value=1.0, nonce=0)
    evm_tx = Transaction(
        from_addr="0xa",
        to_addr="0x" + "0" * 40,
        value=0.0,
        nonce=1,
        data="600760005500",
        gas=100_000,
    )
    assert bc._block_transactions_are_mixed([simple, evm_tx]) is True
    assert bc._block_transactions_are_mixed([simple]) is False
    assert bc._block_transactions_are_all_evm([evm_tx]) is True


def test_mixed_block_simple_then_deploy():
    assert native.native_available()
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "m.db")
    cfg = Config()
    cfg.db_path = path
    cfg.miner_address = "0x" + "f" * 40
    cfg.burn_address = "0x" + "d" * 40
    cfg.evm_enabled = True
    cfg.require_signatures = False
    db = Database(path)
    db.initialize()
    bus = EventBus()
    bc = Blockchain(cfg, db, bus)
    bc.evm = EVMAdapter(db, cfg)

    sender = "0x" + "a1" * 20
    recv = "0x" + "b2" * 20
    db.set_balance(sender, 200.0)
    db.set_balance(cfg.miner_address, 0.0)

    simple = Transaction(from_addr=sender, to_addr=recv, value=5.0, nonce=0)
    deploy = Transaction(
        from_addr=sender,
        to_addr="0x" + "0" * 40,
        value=0.0,
        nonce=1,
        data="600760005500",
        gas=500_000,
    )
    assert bc._block_transactions_are_mixed([simple, deploy]) is True

    block = bc.create_block([simple, deploy], cfg.miner_address)
    assert len(block.transactions) == 2
    assert bc.add_block(block) is True

    assert db.get_balance(recv) == 5.0
    assert block.transactions[0].status == 1
    assert block.transactions[1].status == 1
    rcpt_s = db.get_tx_receipt(block.transactions[0].hash)
    rcpt_d = db.get_tx_receipt(block.transactions[1].hash)
    assert rcpt_s and rcpt_s["status"] == 1
    assert rcpt_d and rcpt_d["status"] == 1

    contracts = [
        a
        for a in db.get_all_accounts()
        if a.get("code") and a["address"].lower() != sender.lower()
    ]
    assert len(contracts) >= 1
