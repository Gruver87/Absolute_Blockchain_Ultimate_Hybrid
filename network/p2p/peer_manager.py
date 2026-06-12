# -*- coding: utf-8 -*-
"""Peer manager with scoring for legacy P2P tests."""
import time
from typing import Dict, Optional


class Peer:
    def __init__(self, peer_id: str, host: str, port: int):
        self.peer_id = peer_id
        self.host = host
        self.port = port
        self.score = 100
        self.is_banned = False
        self._rate_limits: Dict[str, float] = {}

    def touch_rate(self, action: str) -> None:
        self._rate_limits[action] = time.time()


class PeerManager:
    SCORE_DELTAS = {
        "valid_block": 10,
        "invalid_block": -15,
        "malicious": -25,
    }

    def __init__(self, node_id: str = "default_node", port: Optional[int] = None, max_peers: int = 50):
        self.node_id = node_id
        self.port = port
        self.max_peers = max_peers
        self.peers: Dict[str, Peer] = {}

    def add_peer(self, peer_id: str, host: str = "", port: int = 0):
        if len(self.peers) >= self.max_peers:
            return None
        peer = Peer(peer_id, host, port)
        self.peers[peer_id] = peer
        return peer

    def remove_peer(self, peer_id: str) -> None:
        self.peers.pop(peer_id, None)

    def get_peer(self, peer_id: str) -> Optional[Peer]:
        return self.peers.get(peer_id)

    def get_peer_count(self) -> int:
        return len(self.peers)

    def get_peers(self):
        return list(self.peers.keys())

    def update_score(self, peer_id: str, event: str) -> None:
        peer = self.peers.get(peer_id)
        if not peer:
            return
        peer.score += self.SCORE_DELTAS.get(event, 0)
        if peer.score <= 0:
            peer.is_banned = True

    def check_rate_limit(self, peer_id: str, action: str) -> bool:
        peer = self.peers.get(peer_id)
        if not peer:
            return False
        peer.touch_rate(action)
        return True

    def get_stats(self) -> Dict:
        return {
            "total_peers": len(self.peers),
            "connected_peers": len(self.peers),
            "node_id": self.node_id,
        }
