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


def test_build_sync_status_includes_state_root():
    status = _build_sync_status(None, _FakeP2P(), _FakeBC(), Config())
    assert status["state_root"] == "abc123" * 8
    assert status["state_consistent"] is True
    assert status["local_height"] == 10


def test_p2p_state_message_types():
    assert MSG_ATTESTATION == "attestation"
    assert MSG_STATE_ROOT_REQUEST == "state_root_request"
    assert MSG_STATE_ROOT_RESPONSE == "state_root_response"


def test_bridge_lock_arity():
    from bridge.abs_bridge import RustBridge
    import inspect
    sig = inspect.signature(RustBridge.lock_and_bridge)
    params = list(sig.parameters.keys())
    assert params == ["self", "from_addr", "to_chain", "to_addr", "amount"]


def test_sync_state_wire_protocol(monkeypatch):
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
