# -*- coding: utf-8 -*-
"""Block sync manager for legacy v50 tests."""
from typing import Any, Dict, List, Optional


class SyncManager:
    def __init__(self, node: Any):
        self.node = node
        self.syncing = False
        self._peers: Dict[str, Dict] = {}

    def update_peer_state(self, peer_id: str, height: int, head_hash: str) -> None:
        self._peers[peer_id] = {"height": height, "head_hash": head_hash}

    def get_peer_height(self, peer_id: str) -> int:
        return int(self._peers.get(peer_id, {}).get("height", 0))

    def get_best_peer(self) -> Optional[str]:
        if not self._peers:
            return None
        return max(self._peers.items(), key=lambda item: item[1]["height"])[0]

    def needs_sync(self) -> bool:
        local = self._get_local_height()
        best = max((p["height"] for p in self._peers.values()), default=local)
        return best > local

    def handle_block_announce(self, peer_id: str, block_hash: str, height: int) -> None:
        self.update_peer_state(peer_id, max(height, self.get_peer_height(peer_id)), block_hash)

    def get_stats(self) -> Dict:
        return {
            "tracked_peers": len(self._peers),
            "best_peer": self.get_best_peer(),
            "needs_sync": self.needs_sync(),
        }

    def _get_local_height(self) -> int:
        storage = getattr(self.node, "storage", None)
        if storage and hasattr(storage, "get_latest_block_number"):
            return int(storage.get_latest_block_number())
        return 0

    def _get_blocks_from_height(self, start: int, limit: int = 5) -> List[Dict]:
        """Fetch real blocks from node storage (legacy v50 tests only)."""
        storage = getattr(self.node, "storage", None)
        if not storage:
            return []
        get_block = getattr(storage, "get_block", None)
        if not callable(get_block):
            return []
        blocks: List[Dict] = []
        for i in range(limit):
            height = start + i
            blk = get_block(height)
            if not blk:
                break
            blocks.append({
                "number": height,
                "hash": blk.get("hash") or blk.get("block_hash") or "",
            })
        return blocks

    def start_sync(self, peer_id: str) -> bool:
        if peer_id not in self._peers:
            return False
        if self.get_peer_height(peer_id) <= self._get_local_height():
            return False
        self.syncing = True
        return True

    def finish_sync(self) -> None:
        self.syncing = False

    def get_status(self) -> Dict:
        return {"syncing": self.syncing, "best_peer": self.get_best_peer()}
