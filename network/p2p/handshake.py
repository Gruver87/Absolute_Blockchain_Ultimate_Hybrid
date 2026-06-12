# -*- coding: utf-8 -*-
"""P2P handshake protocol for legacy tests."""
from typing import Dict, Tuple

NETWORK_ID = 45


class HandshakeProtocol:
    def __init__(self, node_id: str, head_hash: str, head_height: int, network_id: int = NETWORK_ID):
        self.node_id = node_id
        self.head_hash = head_hash
        self.head_height = head_height
        self.network_id = network_id

    def create_handshake(self) -> Dict:
        return {
            "node_id": self.node_id,
            "version": "45.0",
            "network_id": self.network_id,
            "head_hash": self.head_hash,
            "head_height": self.head_height,
        }

    def validate_handshake(self, handshake: Dict) -> Tuple[bool, str]:
        if handshake.get("network_id") != self.network_id:
            return False, "wrong network_id"
        if not handshake.get("node_id"):
            return False, "missing node_id"
        if not handshake.get("version"):
            return False, "missing version"
        return True, ""
