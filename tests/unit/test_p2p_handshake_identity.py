#!/usr/bin/env python3
"""Handshake rejects when TLS CN/SAN does not match claimed node_id."""

import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

from network.p2p_node import PeerConnection, P2PNode
from network import p2p_node as p2p_mod


class _FakeWriter:
    def get_extra_info(self, name, default=None):
        if name == "peername":
            return ("127.0.0.1", 5001)
        return default

    def write(self, _data):
        return None

    def close(self):
        return None

    async def drain(self):
        return None


def test_handshake_rejects_tls_identity_mismatch():
    cfg = SimpleNamespace(
        chain_id=778888,
        node_version="test",
        node_id="local-node",
        p2p_port=5000,
        p2p_tls_enabled=True,
        p2p_tls_bind_identity=True,
        p2p_tls_peer_fingerprints="",
        p2p_rate_limit_strikes=5,
        p2p_ban_seconds=300,
    )
    bc = SimpleNamespace(get_height=lambda: 1, get_last_block=lambda: None)
    node = P2PNode(cfg, bc, mempool=SimpleNamespace())
    peer = PeerConnection(MagicMock(), _FakeWriter())

    async def _run():
        with patch.object(p2p_mod, "p2p_tls_enabled", return_value=True), patch(
            "network.p2p_node.extract_peer_tls_meta",
            return_value={
                "ssl": True,
                "identities": ["docker-prod-mesh-1"],
                "fingerprint_sha256": "abc",
            },
        ), patch.object(
            PeerConnection,
            "recv",
            return_value={
                "type": p2p_mod.MSG_HANDSHAKE_ACK,
                "data": {
                    "chain_id": 778888,
                    "node_id": "evil-node",
                    "height": 1,
                    "head_hash": "",
                    "p2p_port": 5001,
                },
            },
        ), patch.object(PeerConnection, "send", return_value=None):
            ok = await node._do_handshake(peer, initiator=True)
            assert ok is False
            assert node._handshake_rejects >= 1

    asyncio.run(_run())
