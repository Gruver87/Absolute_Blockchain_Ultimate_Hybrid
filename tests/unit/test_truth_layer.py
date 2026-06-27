#!/usr/bin/env python3
"""Truth layer: feature flags, sync status, P2P state protocol, bridge arity."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from features import FeatureFlags
from runtime.config import Config
from api.http import _build_sync_status
from network.p2p_node import (
    MSG_ATTESTATION,
    MSG_STATE_ROOT_REQUEST,
    MSG_STATE_ROOT_RESPONSE,
    MSG_VALIDATOR_REGISTER,
)


class _FakeBC:
    def get_height(self):
        return 10

    def get_state_root(self):
        return "abc123" * 8


class _FakeP2P:
    _state_consistent = True

    def peer_count(self):
        return 1

    def get_peers_info(self):
        return [{"height": 10}]


def test_feature_flags_from_config():
    cfg = Config()
    cfg.feature_nft = False
    cfg.evm_enabled = True
    flags = FeatureFlags.from_config(cfg)
    d = flags.to_api_dict({"evm": object(), "nft": None})
    assert d["evm"]["configured"] is True
    assert d["evm"]["loaded"] is True
    assert d["nft"]["configured"] is False


def test_prod_feature_flags_block_analysis_and_dev_only_modules():
    cfg = Config()
    cfg.deployment_mode = "prod"
    cfg.feature_mev = True
    cfg.feature_ai_agents = True
    flags = FeatureFlags.from_config(cfg)
    d = flags.to_api_dict({"mev": object(), "ai_agents": object()}, cfg)
    assert d["mev"]["enabled"] is False
    assert d["mev"]["tier"] == "analysis"
    assert d["mev"]["prod_blocked_reason"]
    assert d["ai_agents"]["enabled"] is False
    assert d["ai_agents"]["tier"] == "dev-test"
    assert d["ai_agents"]["prod_blocked_reason"]


def test_build_sync_status_includes_state_root():
    status = _build_sync_status(None, _FakeP2P(), _FakeBC(), Config())
    assert status["state_root"] == "abc123" * 8
    assert status["state_consistent"] is True
    assert status["local_height"] == 10


def test_p2p_state_message_types():
    assert MSG_ATTESTATION == "attestation"
    assert MSG_STATE_ROOT_REQUEST == "state_root_request"
    assert MSG_STATE_ROOT_RESPONSE == "state_root_response"
    assert MSG_VALIDATOR_REGISTER == "validator_register"


def test_bridge_lock_arity():
    from bridge.abs_bridge import RustBridge
    import inspect
    sig = inspect.signature(RustBridge.lock_and_bridge)
    params = list(sig.parameters.keys())
    assert params == ["self", "from_addr", "to_chain", "to_addr", "amount", "l1_tx_hash"]


def test_state_root_strict_above_baseline():
    from core.blockchain import Blockchain
    from runtime.config import Config
    from storage.database import Database
    from kernel.event_bus import EventBus
    import tempfile
    import os

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    cfg = Config()
    cfg.db_path = path
    cfg.verify_peer_state_root = True
    db = Database(path)
    db.initialize()
    bc = Blockchain(cfg, db, EventBus())
    bc.set_state_root_baseline(5)
    assert bc._state_root_check_mode(5, "a" * 64, True) == "legacy_warn"
    assert bc._state_root_check_mode(6, "b" * 64, True) == "strict"
    assert bc._state_root_check_mode(6, "b" * 64, False) == "strict"
    assert bc._state_root_check_mode(6, "abc", True) == "legacy_warn"
    db.close()
    os.remove(path)


def test_evm_deploy_deterministic_address():
    from execution.evm_adapter import EVMAdapter
    from runtime.config import Config
    from storage.database import Database
    import tempfile
    import os

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    cfg = Config()
    db = Database(path)
    db.initialize()
    db.set_balance("0x" + "1" * 40, 100.0)
    evm = EVMAdapter(db, cfg)
    bytecode = "600160005260206000f3"  # minimal init
    r1 = evm.deploy_contract("0x" + "1" * 40, bytecode, salt="1:0:abc")
    r2 = evm.deploy_contract("0x" + "1" * 40, bytecode, salt="1:0:abc")
    assert r1.success and r2.success
    assert r1.return_value == r2.return_value
    db.close()
    os.remove(path)


def test_mempool_tx_carries_data():
    from blockchain.mempool import Mempool, MempoolTransaction

    mp = Mempool()
    tx = MempoolTransaction(
        tx_hash="abc",
        from_addr="0x" + "1" * 40,
        to_addr="0x" + "0" * 40,
        amount=0.0,
        fee=0.01,
        nonce=0,
        data="0x600160005260206000f3",
        gas=500000,
    )
    assert mp.add_raw(tx)
    got = mp.get(limit=1)[0]
    assert got.data.startswith("0x")
    assert got.gas == 500000


def test_consensus_get_attestations_empty():
    from consensus.adapter import ConsensusAdapter
    from runtime.config import Config
    from storage.database import Database
    from kernel.event_bus import EventBus
    import tempfile
    import os

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    cfg = Config()
    db = Database(path)
    db.initialize()
    ca = ConsensusAdapter(cfg, db, EventBus())
    votes = ca.get_attestations()
    assert isinstance(votes, list)
    db.close()
    os.remove(path)


def test_wallet_sign_verify_with_calldata():
    from crypto.wallet import Wallet, verify_transaction_signature

    w = Wallet.create_new()
    zero = "0x0000000000000000000000000000000000000000"
    data = "0x600160005260206000f3"
    signed = w.sign_transaction(zero, 0, 0, chain_id=77777, data=data, gas_limit=500000)
    assert verify_transaction_signature(signed)
    plain = w.sign_transaction("0x" + "b" * 40, 1, 0, chain_id=77777)
    assert verify_transaction_signature(plain)


def test_attestations_by_block_aggregate():
    from consensus.adapter import ConsensusAdapter
    from runtime.config import Config
    from storage.database import Database
    from kernel.event_bus import EventBus
    import tempfile
    import os

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    cfg = Config()
    db = Database(path)
    db.initialize()
    ca = ConsensusAdapter(cfg, db, EventBus())
    if ca.slashing_engine:
        v1, v2 = "0x" + "a" * 40, "0x" + "b" * 40
        ca.slashing_engine.add_validator(v1, 1000)
        ca.slashing_engine.add_validator(v2, 1000)
        ca.slashing_engine.on_attestation(v1, "block_hash_1", 1)
        ca.slashing_engine.on_attestation(v2, "block_hash_1", 1)
        rows = ca.get_attestations_by_block()
        assert any(r["block_hash"] == "block_hash_1" and r["votes"] == 2 for r in rows)
    db.close()
    os.remove(path)


def test_sync_state_wire_protocol():
    from sync.sync_engine import SyncEngine

    class Node:
        def __init__(self):
            self.blockchain = _FakeBC()
            self._state_consistent = True
            self.peers = []

        def request_peer_state_roots_sync(self, timeout=15):
            return [{"peer_id": "peer-1", "height": 10, "state_root": "abc123" * 8}]

    node = Node()
    engine = SyncEngine(node=node)
    assert engine.sync_state() is True

    node.request_peer_state_roots_sync = lambda timeout=15: [
        {"peer_id": "peer-2", "height": 10, "state_root": "deadbeef" * 8}
    ]
    assert engine.sync_state() is False
    assert node._state_consistent is False
