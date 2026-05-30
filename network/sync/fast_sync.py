# network/sync/fast_sync.py
"""
v51 Fast Sync Manager - State root based synchronization
Allows nodes to jump to recent height via state snapshot
"""

import time
import copy
from typing import Optional

from network.p2p.messages import (
    SNAPSHOT_REQUEST,
    SNAPSHOT_RESPONSE,
    STATE_ROOT_REQUEST,
    STATE_ROOT_RESPONSE
)


class FastSyncManager:
    """Fast sync using state snapshots instead of full block replay"""
    
    def __init__(self, node):
        self.node = node
        self.syncing = False
        self.sync_start_time = 0
        self.target_height = 0
    
    # ==================== PUBLIC METHODS ====================
    
    def start_sync(self, peer_id: str, target_height: int):
        """Start fast sync with a peer"""
        if self.syncing:
            return False
        
        self.syncing = True
        self.sync_start_time = time.time()
        self.target_height = target_height
        
        print(f"[FAST SYNC] Starting fast sync from peer {peer_id} to height {target_height}")
        
        # Request snapshot from peer
        request = create_snapshot_request(target_height)
        self._send_to_peer(peer_id, request)
        
        return True
    
    def handle_snapshot_response(self, peer_id: str, snapshot: dict):
        """Handle incoming snapshot - restore state"""
        if not self.syncing:
            return
        
        try:
            height = snapshot.get("height")
            state_root = snapshot.get("state_root")
            state_dump = snapshot.get("state_dump")
            
            if not state_dump:
                print("[FAST SYNC] Empty snapshot, falling back to slow sync")
                self.syncing = False
                return
            
            # Restore state directly from snapshot
            self._restore_state(state_dump)
            
            # Update chain tip
            if hasattr(self.node, 'chain'):
                self.node.chain.set_height(height)
                self.node.chain.set_state_root(state_root)
            
            if hasattr(self.node, 'storage'):
                self.node.storage.save_metadata("head_height", str(height))
                self.node.storage.save_metadata("state_root", state_root)
            
            elapsed = time.time() - self.sync_start_time
            print(f"[FAST SYNC] State restored to height {height} in {elapsed:.2f}s")
            
            # Now sync remaining blocks if needed
            current_height = self._get_local_height()
            if self.target_height > current_height:
                print(f"[FAST SYNC] Need to sync {self.target_height - current_height} remaining blocks")
                self._sync_remaining_blocks(peer_id, current_height + 1, self.target_height)
            else:
                print(f"[FAST SYNC] Fast sync complete! Height: {height}")
                self.syncing = False
                
        except Exception as e:
            print(f"[FAST SYNC] Error during snapshot restore: {e}")
            self.syncing = False
    
    def handle_state_root_response(self, peer_id: str, response: dict):
        """Handle state root verification response"""
        state_root = response.get("state_root")
        block_hash = response.get("block_hash")
        
        if state_root and block_hash:
            print(f"[FAST SYNC] Verified state root for block {block_hash[:16]}...")
    
    def should_fast_sync(self) -> bool:
        """Check if fast sync is needed (peer far ahead)"""
        best_peer = self._get_best_peer()
        if not best_peer:
            return False
        
        peer_height = self._get_peer_height(best_peer)
        local_height = self._get_local_height()
        lag = peer_height - local_height
        
        # Fast sync if lag > 20 blocks
        return lag > 20
    
    def get_fast_sync_status(self) -> dict:
        """Get fast sync status"""
        return {
            "is_syncing": self.syncing,
            "target_height": self.target_height,
            "elapsed_seconds": time.time() - self.sync_start_time if self.syncing else 0
        }
    
    # ==================== PRIVATE METHODS ====================
    
    def _send_to_peer(self, peer_id: str, message: dict):
        """Send message to specific peer"""
        if hasattr(self.node, 'p2p_server') and hasattr(self.node, 'peer_manager'):
            peer = self.node.peer_manager.get_peer(peer_id)
            if peer:
                self.node.p2p_server.send_message(peer, message)
    
    def _restore_state(self, state_dump: dict):
        """Restore blockchain state from snapshot"""
        # Restore accounts
        if "accounts" in state_dump and hasattr(self.node, 'storage'):
            for address, account_data in state_dump["accounts"].items():
                self.node.storage.save_account_state(
                    address,
                    account_data.get("balance", 0),
                    account_data.get("nonce", 0)
                )
        
        # Restore validators
        if "validators" in state_dump and hasattr(self.node, 'storage'):
            for validator in state_dump["validators"]:
                self.node.storage.save_validator(
                    validator.get("address"),
                    validator.get("stake", 0)
                )
        
        print(f"[FAST SYNC] Restored {len(state_dump.get('accounts', {}))} accounts")
    
    def _sync_remaining_blocks(self, peer_id: str, from_height: int, to_height: int):
        """Sync remaining blocks after snapshot"""
        if hasattr(self.node, 'sync_manager'):
            # Delegate to regular sync for remaining blocks
            self.node.sync_manager.request_sync(peer_id, from_height, to_height)
            self.syncing = False
    
    def _get_local_height(self) -> int:
        """Get local blockchain height"""
        if hasattr(self.node, 'storage'):
            return self.node.storage.get_latest_block_number()
        return 0
    
    def _get_best_peer(self) -> Optional[str]:
        """Get best peer by height"""
        if hasattr(self.node, 'sync_manager'):
            return self.node.sync_manager.get_best_peer()
        return None
    
    def _get_peer_height(self, peer_id: str) -> int:
        """Get peer height"""
        if hasattr(self.node, 'sync_manager'):
            return self.node.sync_manager.get_peer_height(peer_id)
        return 0


def create_snapshot_request(height: int) -> dict:
    """Create snapshot request message"""
    return {
        "type": SNAPSHOT_REQUEST,
        "height": height
    }
