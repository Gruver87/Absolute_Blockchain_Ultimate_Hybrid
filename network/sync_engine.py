# -*- coding: utf-8 -*-
"""Header-first sync engine for legacy tests."""
from typing import Any, Dict, List, Optional


class SyncEngine:
    def __init__(self, node: Any):
        self.node = node
        self.peers: List[Any] = []
        self.syncing = False
        self._best_peer: Optional[Any] = None

    def add_peer(self, peer: Any) -> None:
        self.peers.append(peer)

    def get_peer_count(self) -> int:
        return len(self.peers)

    def select_best_peer(self) -> Optional[Any]:
        if not self.peers:
            return None
        self._best_peer = max(self.peers, key=lambda p: getattr(p, "height", 0))
        return self._best_peer

    def start_sync(self) -> bool:
        best = self.select_best_peer()
        if not best:
            return False
        self.syncing = True
        headers = best.get_headers(start=0, limit=100)
        for header in headers:
            self.node.chain.add_header(header)
            if header["hash"] not in self.node.chain.blocks:
                body = best.get_block(header["hash"])
                if body:
                    self.node.chain.add_block(body)
        self._finalize_sync()
        return True

    def _finalize_sync(self) -> None:
        self.syncing = False

    def get_status(self) -> Dict:
        best_height = getattr(self._best_peer, "height", 0) if self._best_peer else 0
        return {
            "syncing": self.syncing,
            "peers": len(self.peers),
            "best_peer_height": best_height,
            "local_height": self.node.chain.get_head_height(),
        }
