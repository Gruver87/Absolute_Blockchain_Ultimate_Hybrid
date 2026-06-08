# network/p2p/handshake.py
"""
Peer handshake protocol — initial connection validation
"""

import time
import json
from typing import Dict, Any, Optional, Tuple


class HandshakeError(Exception):
    pass


class HandshakeProtocol:
    """Handshake validator for peer connections"""
    
    PROTOCOL_VERSION = "45.0"
    NETWORK_ID = 1
    
    def __init__(self, node_id: str, head_hash: str, head_height: int):
        self.node_id = node_id
        self.head_hash = head_hash
        self.head_height = head_height
    
    def create_handshake(self) -> Dict:
        """Create handshake message"""
        return {
            "type": "hello",
            "node_id": self.node_id,
            "version": self.PROTOCOL_VERSION,
            "network_id": self.NETWORK_ID,
            "head_hash": self.head_hash,
            "head_height": self.head_height,
            "timestamp": time.time()
        }
    
    def validate_handshake(self, handshake: Dict) -> Tuple[bool, str]:
        """
        Validate incoming handshake
        Returns: (is_valid, error_message)
        """
        # Check required fields
        required = ["node_id", "version", "network_id", "head_hash", "head_height"]
        for field in required:
            if field not in handshake:
                return False, f"Missing field: {field}"
        
        # Check network id
        if handshake["network_id"] != self.NETWORK_ID:
            return False, f"Wrong network id: {handshake['network_id']} != {self.NETWORK_ID}"
        
        # Check version compatibility
        if handshake["version"] != self.PROTOCOL_VERSION:
            return False, f"Incompatible version: {handshake['version']} != {self.PROTOCOL_VERSION}"
        
        # Check node id not self
        if handshake["node_id"] == self.node_id:
            return False, "Cannot connect to self"
        
        # Valid handshake
        return True, ""
    
    def create_ping(self) -> Dict:
        """Create ping message"""
        return {
            "type": "ping",
            "timestamp": time.time()
        }
    
    def create_pong(self, ping_time: float) -> Dict:
        """Create pong response"""
        return {
            "type": "pong",
            "ping_time": ping_time,
            "pong_time": time.time()
        }
    
    def validate_pong(self, pong: Dict, ping_time: float) -> float:
        """Calculate latency from ping-pong"""
        if "pong_time" not in pong:
            return -1
        return pong["pong_time"] - ping_time
