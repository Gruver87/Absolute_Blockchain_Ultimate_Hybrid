# network/sync/sync_manager.py
"""
v50 Block Sync & Peer State Sync Engine
Handles: block propagation, chain sync, fork detection, peer tracking
"""

import time
import threading
from collections import defaultdict
from typing import Dict, Optional, List

from network.p2p.messages import (
    MessageType,
    create_block_announce,
    create_block_request,
    create_block_response,
    create_sync_request,
    create_sync_response
)


class SyncManager:
    """Manages blockchain synchronization between peers"""
    
    def __init__(self, node):
        self.node = node
        self.peers_state: Dict[str, dict] = {}  # peer_id -> {height, best_hash, last_seen}
        self.pending_block_requests: Dict[str, str] = {}  # peer_id -> block_hash
        self.sync_in_progress = False
        self.sync_lock = threading.RLock()
        
    # ==================== PEER TRACKING ====================
    
    def update_peer_state(self, peer_id: str, height: int, best_hash: str):
        """Track peer's blockchain height"""
        self.peers_state[peer_id] = {
            "height": height,
            "best_hash": best_hash,
            "last_seen": time.time()
        }
    
    def get_best_peer(self) -> Optional[str]:
        """Get peer with highest block height"""
        if not self.peers_state:
            return None
        return max(self.peers_state.items(), key=lambda x: x[1]["height"])[0]
    
    def get_peer_height(self, peer_id: str) -> int:
        """Get peer's known height"""
        peer = self.peers_state.get(peer_id)
        return peer["height"] if peer else 0
    
    def needs_sync(self) -> bool:
        """Check if this node needs to sync with peers"""
        my_height = self._get_local_height()
        best_peer = self.get_best_peer()
        if not best_peer:
            return False
        best_height = self.peers_state[best_peer]["height"]
        return best_height > my_height + 1
    
    # ==================== BLOCK PROPAGATION ====================
    
    def announce_new_block(self, block: dict):
        """Broadcast new block to all peers"""
        block_hash = block.get("hash")
        height = block.get("number", 0)
        
        announce = create_block_announce(block_hash, height)
        
        # Broadcast to all connected peers
        if hasattr(self.node, 'p2p_server'):
            self.node.p2p_server.broadcast(announce)
            print(f"📢 Announced new block #{height}: {block_hash[:16]}...")
    
    def handle_block_announce(self, peer_id: str, block_hash: str, height: int):
        """Handle incoming block announcement"""
        self.update_peer_state(peer_id, height, block_hash)
        
        my_height = self._get_local_height()
        
        # If we're behind, request the block
        if height > my_height or not self._has_block(block_hash):
            self.request_block(peer_id, block_hash)
    
    def request_block(self, peer_id: str, block_hash: str):
        """Request a specific block from peer"""
        request = create_block_request(block_hash)
        self.pending_block_requests[peer_id] = block_hash
        
        if hasattr(self.node, 'p2p_server'):
            # Send to specific peer
            peer = self.node.peer_manager.get_peer(peer_id)
            if peer:
                self.node.p2p_server.send_message(peer, request)
    
    def handle_block_response(self, block: dict):
        """Handle incoming block response"""
        if not block:
            return
        
        # Import block using block importer
        if hasattr(self.node, 'block_importer'):
            success = self.node.block_importer.import_block(block)
            if success:
                print(f"📦 Imported block #{block.get('number')}: {block.get('hash', '')[:16]}...")
    
    # ==================== CHAIN SYNC ====================
    
    def request_sync(self, peer_id: str):
        """Request chain sync from peer"""
        my_height = self._get_local_height()
        request = create_sync_request(my_height)
        
        if hasattr(self.node, 'p2p_server'):
            peer = self.node.peer_manager.get_peer(peer_id)
            if peer:
                self.node.p2p_server.send_message(peer, request)
                print(f"🔄 Requested sync from {peer_id} from height {my_height}")
    
    def handle_sync_request(self, peer_id: str, from_height: int):
        """Handle incoming sync request - send missing blocks"""
        blocks = self._get_blocks_from_height(from_height + 1, limit=100)
        
        response = create_sync_response(blocks)
        if hasattr(self.node, 'p2p_server'):
            peer = self.node.peer_manager.get_peer(peer_id)
            if peer:
                self.node.p2p_server.send_message(peer, response)
                print(f"📤 Sent {len(blocks)} blocks to {peer_id}")
    
    def handle_sync_response(self, blocks: List[dict]):
        """Handle sync response - import blocks sequentially"""
        for block in blocks:
            if hasattr(self.node, 'block_importer'):
                success = self.node.block_importer.import_block(block)
                if not success:
                    print(f"⚠️ Failed to import block #{block.get('number')}")
                    break
                print(f"   ✅ Synced block #{block.get('number')}")
    
    def start_background_sync(self):
        """Background thread for automatic sync"""
        def sync_loop():
            while True:
                time.sleep(30)  # Check every 30 seconds
                if self.needs_sync():
                    self.sync_with_best_peer()
        
        thread = threading.Thread(target=sync_loop, daemon=True)
        thread.start()
    
    def sync_with_best_peer(self):
        """Sync with the best available peer"""
        if self.sync_in_progress:
            return
        
        best_peer = self.get_best_peer()
        if not best_peer:
            return
        
        with self.sync_lock:
            self.sync_in_progress = True
            try:
                print(f"🔄 Starting sync with peer {best_peer}")
                self.request_sync(best_peer)
            finally:
                self.sync_in_progress = False
    
    # ==================== HELPER METHODS ====================
    
    def _get_local_height(self) -> int:
        """Get local blockchain height"""
        if hasattr(self.node, 'storage'):
            return self.node.storage.get_latest_block_number()
        return 0
    
    def _has_block(self, block_hash: str) -> bool:
        """Check if block exists locally"""
        if hasattr(self.node, 'storage'):
            block = self.node.storage.get_block(block_hash)
            return block is not None
        return False
    
    def _get_blocks_from_height(self, start_height: int, limit: int = 100) -> List[dict]:
        """Get blocks from height onwards"""
        blocks = []
        if hasattr(self.node, 'storage'):
            for height in range(start_height, start_height + limit):
                block = self.node.storage.get_block_by_number(height)
                if block:
                    blocks.append(block)
                else:
                    break
        return blocks
    
    # ==================== MESSAGE HANDLER ====================
    
    def handle_message(self, peer_id: str, msg: dict):
        """Route v50 sync messages"""
        msg_type = msg.get("type")
        
        if msg_type == MessageType.BLOCK_ANNOUNCE.value:
            self.handle_block_announce(peer_id, msg.get("hash"), msg.get("height"))
        
        elif msg_type == MessageType.BLOCK_RESPONSE.value:
            self.handle_block_response(msg.get("block"))
        
        elif msg_type == MessageType.SYNC_REQUEST.value:
            self.handle_sync_request(peer_id, msg.get("from_height"))
        
        elif msg_type == MessageType.SYNC_RESPONSE.value:
            self.handle_sync_response(msg.get("blocks", []))
        
        elif msg_type == MessageType.GET_HEIGHT.value:
            self._handle_get_height(peer_id)
        
        elif msg_type == MessageType.HEIGHT.value:
            self.update_peer_state(peer_id, msg.get("height"), msg.get("best_hash"))
    
    def _handle_get_height(self, peer_id: str):
        """Respond with current height"""
        height = self._get_local_height()
        best_hash = self.node.storage.get_latest_block().get("hash") if self._get_local_height() > 0 else ""
        
        response = {
            "type": MessageType.HEIGHT.value,
            "height": height,
            "best_hash": best_hash
        }
        
        if hasattr(self.node, 'p2p_server'):
            peer = self.node.peer_manager.get_peer(peer_id)
            if peer:
                self.node.p2p_server.send_message(peer, response)
    
    def get_stats(self) -> dict:
        """Get sync manager statistics"""
        return {
            "tracked_peers": len(self.peers_state),
            "best_peer": self.get_best_peer(),
            "needs_sync": self.needs_sync(),
            "local_height": self._get_local_height()
        }


# Add to __init__ method:
# self.fast_sync = None  # Will be set after creation

def init_fast_sync(self, fast_sync):
    """Initialize fast sync manager"""
    self.fast_sync = fast_sync

def maybe_fast_sync(self):
    """Check and trigger fast sync if needed"""
    if self.fast_sync and self.fast_sync.should_fast_sync():
        best_peer = self.get_best_peer()
        if best_peer:
            peer_height = self.peers_state[best_peer]["height"]
            print(f"[SYNC] Lag detected: local={self._get_local_height()}, peer={peer_height}")
            print("[SYNC] Switching to FAST SYNC mode")
            self.fast_sync.start_sync(best_peer, peer_height)
            return True
    return False

def request_sync_range(self, peer_id: str, from_height: int, to_height: int):
    """Request a range of blocks from peer"""
    for height in range(from_height, to_height + 1):
        # Request block by height
        pass  # Implement block range request
