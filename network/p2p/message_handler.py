# network/p2p/message_handler.py
"""
Message handler with routing and response generation
"""

from typing import Optional

from network.p2p.messages import Message, MessageType, InventoryMessage, CompactBlock
from network.p2p.peer_manager import PeerManager


class MessageHandler:
    """Handles incoming P2P messages"""
    
    def __init__(self, peer_manager: PeerManager, mempool, block_importer, 
                 state_engine, p2p_server):
        self.peer_manager = peer_manager
        self.mempool = mempool
        self.block_importer = block_importer
        self.state_engine = state_engine
        self.p2p_server = p2p_server
        
        self.handlers = {
            MessageType.HELLO: self._handle_hello,
            MessageType.PING: self._handle_ping,
            MessageType.PONG: self._handle_pong,
            MessageType.INV_BLOCK: self._handle_inv_block,
            MessageType.GET_BLOCK: self._handle_get_block,
            MessageType.BLOCK: self._handle_block,
            MessageType.INV_TX: self._handle_inv_tx,
            MessageType.GET_TX: self._handle_get_tx,
            MessageType.TX: self._handle_tx,
            MessageType.GET_HEADERS: self._handle_get_headers,
            MessageType.STATUS: self._handle_status,
        }
    
    def handle_message(self, message: Message, from_peer_id: str) -> Optional[Message]:
        """Route message to appropriate handler"""
        # Check rate limit
        if not self.peer_manager.check_rate_limit(from_peer_id, message.type.value):
            return None
        
        handler = self.handlers.get(message.type)
        if handler:
            return handler(message, from_peer_id)
        return None
    
    def _handle_hello(self, msg: Message, from_peer_id: str) -> Optional[Message]:
        """Handle handshake"""
        data = msg.data
        version = data.get("version")
        network_id = data.get("network_id")
        
        # Check compatibility
        if version != "45.0" or network_id != 1:
            self.peer_manager.update_score(from_peer_id, "malicious")
            return None
        
        # Update peer info
        self.peer_manager.update_head(
            from_peer_id, 
            data.get("head_hash", ""),
            data.get("head_height", 0)
        )
        
        # Respond with status
        return Message(MessageType.STATUS, {
            "height": self.state_engine.get_current_height(),
            "hash": self.state_engine.get_head_hash()
        })
    
    def _handle_ping(self, msg: Message, from_peer_id: str) -> Message:
        """Respond to ping"""
        self.peer_manager.update_last_ping(from_peer_id)
        return Message(MessageType.PONG, {"pong_time": time.time()})
    
    def _handle_pong(self, msg: Message, from_peer_id: str) -> None:
        """Update latency"""
        self.peer_manager.update_score(from_peer_id, "fast_response")
    
    def _handle_inv_block(self, msg: Message, from_peer_id: str) -> None:
        """Handle block inventory announcement"""
        block_hash = msg.data.get("hash")
        # If we don't have this block, request it
        # Would check local storage
        pass
    
    def _handle_get_block(self, msg: Message, from_peer_id: str) -> Optional[Message]:
        """Return requested block"""
        block_hash = msg.data.get("hash")
        block_number = msg.data.get("number")
        # Would fetch from storage
        return Message(MessageType.BLOCK, {"block": None})
    
    def _handle_block(self, msg: Message, from_peer_id: str) -> None:
        """Process incoming block"""
        block = msg.data.get("block")
        if block:
            # Update peer score
            self.peer_manager.update_score(from_peer_id, "valid_block")
            # Import block
            parent = self.state_engine.get_parent_block(block.get("parent_hash"))
            success, _ = self.block_importer.import_block(block, parent)
            if success:
                # Gossip to other peers
                self.p2p_server.broadcast(msg, exclude_peer_id=from_peer_id)
    
    def _handle_inv_tx(self, msg: Message, from_peer_id: str) -> None:
        """Handle transaction inventory"""
        tx_hash = msg.data.get("hash")
        # Request full tx if we don't have it
        pass
    
    def _handle_get_tx(self, msg: Message, from_peer_id: str) -> Optional[Message]:
        """Return requested transaction"""
        tx_hash = msg.data.get("hash")
        tx = self.mempool.get_transaction(tx_hash)
        if tx:
            return Message(MessageType.TX, {"transaction": tx})
        return None
    
    def _handle_tx(self, msg: Message, from_peer_id: str) -> None:
        """Process incoming transaction"""
        tx = msg.data.get("transaction")
        if tx:
            self.peer_manager.update_score(from_peer_id, "valid_tx")
            self.mempool.add_transaction(tx)
            self.p2p_server.broadcast(msg, exclude_peer_id=from_peer_id)
    
    def _handle_get_headers(self, msg: Message, from_peer_id: str) -> Optional[Message]:
        """Return block headers for sync"""
        from_hash = msg.data.get("from")
        limit = msg.data.get("limit", 64)
        # Would fetch headers from storage
        return Message(MessageType.HEADERS, {"headers": []})
    
    def _handle_status(self, msg: Message, from_peer_id: str) -> Optional[Message]:
        """Update peer status"""
        height = msg.data.get("height", 0)
        self.peer_manager.update_head(from_peer_id, "", height)
        return None


import time

# network/p2p/message_handler.py (v50 update)

# Add sync routing to existing message handler
# Add this method to your existing MessageHandler class:

def handle_message_v50(self, peer_id: str, msg: dict):
    """Route v50 sync messages to sync manager"""
    if self.node and hasattr(self.node, 'sync_manager'):
        self.node.sync_manager.handle_message(peer_id, msg)
        return True
    return False
