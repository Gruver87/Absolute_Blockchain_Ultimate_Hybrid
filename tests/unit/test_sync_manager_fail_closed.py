import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from network.sync.fast_sync import FastSyncManager
from network.sync.sync_manager import SyncManager


class _Storage:
    def __init__(self, height: int):
        self.height = height

    def get_latest_block_number(self):
        return self.height


class _PeerSync:
    def __init__(self, heights):
        self.heights = heights

    def get_peer_height(self, peer_id):
        return self.heights.get(peer_id, 0)

    def get_best_peer(self):
        if not self.heights:
            return None
        return max(self.heights, key=self.heights.get)


class _Node:
    def __init__(self, height: int, peer_heights=None):
        self.storage = _Storage(height)
        self.sync_manager = _PeerSync(peer_heights or {})


def test_sync_manager_start_requires_known_ahead_peer():
    mgr = SyncManager(_Node(height=10))

    assert mgr.start_sync("missing") is False

    mgr.update_peer_state("peer-low", height=10, head_hash="0x10")
    assert mgr.start_sync("peer-low") is False

    mgr.update_peer_state("peer-high", height=12, head_hash="0x12")
    assert mgr.start_sync("peer-high") is True


def test_fast_sync_start_requires_target_above_local_and_peer_height():
    mgr = FastSyncManager(_Node(height=100, peer_heights={"peer1": 110}))

    assert mgr.start_sync("peer1", target_height=100) is False
    assert mgr.start_sync("peer1", target_height=111) is False
    assert mgr.start_sync("peer1", target_height=110) is True


def test_fast_sync_complete_requires_active_sync():
    mgr = FastSyncManager(_Node(height=1, peer_heights={"peer1": 3}))

    assert mgr.complete_fast_sync() is False
    assert mgr.start_sync("peer1", target_height=3) is True
    assert mgr.complete_fast_sync() is True
