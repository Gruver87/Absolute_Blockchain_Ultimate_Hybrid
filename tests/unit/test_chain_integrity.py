#!/usr/bin/env python3
"""Chain integrity: signatures, state_root, proposer, reorg."""
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
from crypto.wallet import Wallet


@pytest.fixture
def chain_env():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    cfg = Config()
    cfg.db_path = path
    cfg.require_signatures = True
    cfg.miner_address = "0x" + "a" * 40
    cfg.founder_address = cfg.miner_address
    db = Database(path)
    db.initialize()
    bus = EventBus()
    bc = Blockchain(cfg, db, bus)
    yield cfg, db, bc
    db.close()
    try:
        os.remove(path)
    except OSError:
        pass


def test_unsigned_tx_rejected_when_required(chain_env):
    cfg, db, bc = chain_env
    sender = Wallet()
    db.set_balance(sender.address, 1000.0)
    mp = Mempool()
    mp.set_blockchain(bc)

    tx = MempoolTransaction(
        tx_hash="unsigned1",
        from_addr=sender.address,
        to_addr="0x" + "b" * 40,
        amount=1.0,
        fee=0.01,
        nonce=0,
    )
    assert mp.add(tx) is False


def test_signed_tx_accepted(chain_env):
    cfg, db, bc = chain_env
    sender = Wallet()
    db.set_balance(sender.address, 1000.0)
    mp = Mempool()
    mp.set_blockchain(bc)

    raw = sender.sign_transaction("0x" + "b" * 40, 1, nonce=0, chain_id=cfg.chain_id)
    tx = MempoolTransaction(
        tx_hash=raw["hash"],
        from_addr=raw["from"],
        to_addr=raw["to"],
        amount=float(raw["value"]),
        fee=0.01,
        nonce=raw["nonce"],
        signature=raw["signature"],
        public_key=raw["public_key"],
    )
    assert mp.add(tx) is True


def test_state_root_mismatch_rejects_import(chain_env):
    cfg, db, bc = chain_env
    block = bc.create_block([], cfg.miner_address)
    ok = bc.add_block(block)
    assert ok

    peer_block = block.to_dict()
    peer_block["state_root"] = "f" * 64
    assert bc.import_block(peer_block) is False


def test_reorg_replays_state(chain_env):
    cfg, db, bc = chain_env
    for _ in range(3):
        blk = bc.create_block([], cfg.miner_address)
        assert bc.add_block(blk)

    tip = bc.get_height()
    ancestor = tip - 1
    assert bc.reorg_to_ancestor(ancestor) is True
    assert bc.get_height() == ancestor
    assert bc.get_state_root() == db.get_block(ancestor).get("state_root", bc.get_state_root())


def test_slashing_core_resolves_from_adapter(chain_env):
    from consensus.adapter import ConsensusAdapter

    cfg, db, bc = chain_env
    adapter = ConsensusAdapter(cfg, db, None)
    bc.consensus_adapter = adapter
    core = bc._resolve_slashing_core()
    assert core is not None
    assert hasattr(core, "slashed")
    assert hasattr(core, "record_proposal")


def test_add_block_with_consensus_adapter(chain_env):
    from consensus.adapter import ConsensusAdapter

    cfg, db, bc = chain_env
    bc.consensus_adapter = ConsensusAdapter(cfg, db, None)
    blk = bc.create_block([], cfg.miner_address)
    assert bc.add_block(blk) is True
    assert bc.get_height() >= 1


def test_import_allows_equal_timestamp(chain_env):
    cfg, db, bc = chain_env
    parent = bc.create_block([], cfg.miner_address)
    assert bc.add_block(parent)
    ts = parent.timestamp
    child_dict = bc.create_block([], cfg.miner_address).to_dict()
    child_dict["height"] = parent.height + 1
    child_dict["number"] = parent.height + 1
    child_dict["parent_hash"] = parent.hash
    child_dict["timestamp"] = ts
    child_dict["hash"] = "b" * 64
    assert bc.import_block(child_dict) is True
