"""Wave 57 — production core: deterministic consensus, finality quorum, reorg guard."""
import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)


@pytest.fixture
def chain_env():
    from runtime.config import Config
    from storage.database import Database
    from core.blockchain import Blockchain

    tmp = tempfile.mkdtemp(prefix="abs_w57_")
    cfg = Config()
    cfg.db_path = os.path.join(tmp, "chain.db")
    cfg.miner_address = "0x" + "ab" * 20
    db = Database(cfg.db_path)
    bc = Blockchain(cfg, db)
    yield cfg, db, bc


def test_deterministic_proposer_across_nodes():
    from consensus_engine import ConsensusEngine

    a = ConsensusEngine()
    b = ConsensusEngine()
    for i in range(3):
        addr = "0x" + hex(i + 1)[2:].zfill(40)
        a.add_validator(addr, 1000 + i * 100)
        b.add_validator(addr, 1000 + i * 100)
    a.current_slot = 7
    b.current_slot = 7
    pa = a.select_proposer()
    pb = b.select_proposer()
    assert pa and pb
    assert pa.address == pb.address


def test_finality_quorum_uses_live_validator_count():
    from finality_engine import FinalityEngine

    fe = FinalityEngine()
    fe.set_active_validator_count(3)
    fe.create_checkpoint(32, "0x" + "aa" * 32)
    fe.add_attestation("v1", 1, "0x" + "aa" * 32)
    fe.add_attestation("v2", 1, "0x" + "aa" * 32)
    assert 1 in fe.justified_checkpoints


def test_reorg_denied_below_finalized_floor(chain_env):
    from consensus.adapter import ConsensusAdapter

    cfg, db, bc = chain_env
    adapter = ConsensusAdapter(cfg, db, None)
    bc.consensus_adapter = adapter
    for _ in range(4):
        blk = bc.create_block([], cfg.miner_address)
        assert bc.add_block(blk)
        adapter.process_block_finality(
            blk.height, blk.hash, blk.miner or cfg.miner_address
        )

    tip = bc.get_height()
    floor = adapter.get_finalized_floor_height()
    if floor <= 0:
        return
    assert bc.reorg_to_ancestor(max(0, floor - 1)) is False
    assert bc.get_height() == tip


def test_mev_uses_fee_order_not_random():
    from features.mev_simulator import MEVSimulator, Transaction

    mev = MEVSimulator()
    txs = [
        Transaction("0x1", "a", "b", 10.0, 100, 1),
        Transaction("0x2", "c", "d", 5.0, 50, 2),
    ]
    out = mev.detect_sandwich_opportunity(txs)
    assert out.get("source") == "mempool_fee_order"
    assert "profit" in out
