#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""On-chain EVM: signed deploy tx mined into block with real storage."""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.config import Config
from storage.database import Database
from kernel.event_bus import EventBus
from core.blockchain import Blockchain, Transaction
from blockchain.mempool import Mempool, MempoolTransaction
from execution.evm_adapter import EVMAdapter
from crypto.wallet import Wallet


@pytest.fixture
def onchain_env():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    cfg = Config()
    cfg.db_path = path
    cfg.require_signatures = True
    cfg.miner_address = "0x" + "f" * 40
    cfg.evm_enabled = True
    db = Database(path)
    db.initialize()
    bus = EventBus()
    evm = EVMAdapter(db, cfg)
    bc = Blockchain(cfg, db, bus)
    bc.evm = evm
    mp = Mempool()
    mp.set_blockchain(bc)
    wallet = Wallet()
    db.set_balance(wallet.address, 500.0)
    db.set_balance(cfg.miner_address, 0.0)
    yield cfg, db, bc, mp, wallet, evm
    db.close()
    try:
        os.remove(path)
    except OSError:
        pass


def test_signed_evm_deploy_mined_to_block(onchain_env):
    cfg, db, bc, mp, wallet, evm = onchain_env
    bytecode = "600760005500"  # PUSH7, PUSH0, SSTORE, STOP
    zero = "0x0000000000000000000000000000000000000000"
    signed = wallet.sign_transaction(
        zero, 0, nonce=0, chain_id=cfg.chain_id,
        data=bytecode, gas_limit=500_000,
    )
    mp_tx = MempoolTransaction(
        tx_hash=signed["hash"],
        from_addr=signed["from"],
        to_addr=signed["to"],
        amount=0.0,
        fee=0.01,
        nonce=signed["nonce"],
        signature=signed["signature"],
        public_key=signed["public_key"],
        data=bytecode,
        gas=500_000,
    )
    assert mp.add(mp_tx) is True

    block = bc.create_block(
        [Transaction(
            from_addr=mp_tx.from_addr,
            to_addr=mp_tx.to_addr,
            value=0.0,
            nonce=mp_tx.nonce,
            gas=mp_tx.gas,
            data=bytecode,
            signature=mp_tx.signature,
            public_key=mp_tx.public_key,
            tx_hash=mp_tx.tx_hash,
        )],
        cfg.miner_address,
    )
    assert bc.add_block(block) is True

    contracts = [
        a for a in db.get_all_accounts()
        if a.get("code") and a["address"].lower() != wallet.address.lower()
    ]
    assert len(contracts) >= 1
    storage = __import__("json").loads(contracts[0].get("storage") or "{}")
    assert storage.get("0") == 7 or storage.get(0) == 7
