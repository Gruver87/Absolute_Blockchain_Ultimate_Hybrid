# network/sync/sync_manager.py
"""
Header-first sync manager — like Ethereum sync
"""

import time
import threading
from typing import List, Optional


class SyncManager:
    """Manages blockchain synchronization with peers"""
    
    def __init__(self, peer_manager, block_importer, state_engine):
        self.peer_manager = peer_manager
        self.block_importer = block_importer
        self.state_engine = state_engine
        self.is_syncing = False
        self.sync_target_height = 0
        self.sync_progress = 0
        self.sync_lock = threading.Lock()
    
    def should_sync(self) -> bool:
        """Check if we need to sync"""
        current_height = self.state_engine.get_current_height()
        best_peers = self.peer_manager.get_best_peers(1)
        
        if not best_peers:
            return False
        
        best_height = best_peers[0].head_height
        return best_height > current_height + 10
    
    def start_sync(self):
        """Start header-first sync"""
        with self.sync_lock:
            if self.is_syncing:
                return
            
            self.is_syncing = True
            threading.Thread(target=self._sync_loop, daemon=True).start()
    
    def _sync_loop(self):
        """Main sync loop"""
        while self.is_syncing:
            if not self.should_sync():
                self.is_syncing = False
                break
            
            # Get best peer
            best_peers = self.peer_manager.get_best_peers(1)
            if not best_peers:
                break
            
            best_peer = best_peers[0]
            current_height = self.state_engine.get_current_height()
            self.sync_target_height = best_peer.head_height
            
            # Sync in batches
            BATCH_SIZE = 64
            for start in range(current_height + 1, self.sync_target_height + 1, BATCH_SIZE):
                end = min(start + BATCH_SIZE - 1, self.sync_target_height)
                self._sync_batch(best_peer, start, end)
                self.sync_progress = end
        
        self.is_syncing = False
    
    def _sync_batch(self, peer, from_height: int, to_height: int):
        """Sync a batch of blocks"""
        for height in range(from_height, to_height + 1):
            # Request block from peer
            block = self._request_block(peer, height)
            if block:
                parent = self.state_engine.get_parent_block(block.get("parent_hash"))
                success, _ = self.block_importer.import_block(block, parent)
                if success:
                    print(f"   📦 Synced block {height}")
            else:
                break
    
    def _request_block(self, peer, height: int) -> Optional[dict]:
        """Request block by height from peer"""
        # In real implementation, would send GET_BLOCK message
        # For now, return None
        return None
    
    def get_sync_status(self) -> dict:
        return {
            "is_syncing": self.is_syncing,
            "current_height": self.state_engine.get_current_height(),
            "target_height": self.sync_target_height,
            "progress_percent": (self.sync_progress / self.sync_target_height * 100) if self.sync_target_height > 0 else 0
        }
    
    def stop_sync(self):
        self.is_syncing = False
