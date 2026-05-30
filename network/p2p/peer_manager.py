# network/p2p/peer_manager.py
"""
Peer manager with scoring and ban system
"""

import time
import threading
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class Peer:
    """Peer information with scoring"""
    node_id: str
    ip: str
    port: int
    head_hash: str = ""
    head_height: int = 0
    score: int = 100  # Start with neutral score
    latency: float = 0
    connected_since: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    last_ping: float = 0
    is_banned: bool = False
    ban_reason: str = ""
    ban_until: float = 0
    
    # Rate limiting counters
    msg_count: int = 0
    last_reset: float = field(default_factory=time.time)
    block_requests: int = 0
    tx_requests: int = 0
    
    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "ip": self.ip,
            "port": self.port,
            "head_height": self.head_height,
            "score": self.score,
            "latency": self.latency
        }


class PeerManager:
    """Manages peers with scoring, banning, and rate limiting"""
    
    def __init__(self, self_node_id: str, max_peers: int = 50):
        self.self_node_id = self_node_id
        self.max_peers = max_peers
        self.peers: Dict[str, Peer] = {}
        self.banned_ips: Set[str] = set()
        self.lock = threading.RLock()
        
        # Scoring weights
        self.score_weights = {
            "valid_block": 10,
            "valid_tx": 2,
            "fast_response": 1,
            "good_header": 5,
            "invalid_block": -50,
            "invalid_tx": -10,
            "spam": -20,
            "timeout": -15,
            "bad_headers": -30,
            "malicious": -100
        }
        
        # Ban threshold
        self.BAN_THRESHOLD = -100
        self.BAN_DURATION = 3600  # 1 hour
    
    def add_peer(self, node_id: str, ip: str, port: int) -> Optional[Peer]:
        """Add new peer if not banned and under limit"""
        with self.lock:
            # Check if ip is banned
            if ip in self.banned_ips or self._is_ip_banned(ip):
                return None
            
            # Check max peers
            if len(self.peers) >= self.max_peers:
                # Remove lowest scoring peer
                self._remove_lowest_scoring()
            
            peer = Peer(node_id=node_id, ip=ip, port=port)
            self.peers[node_id] = peer
            return peer
    
    def remove_peer(self, node_id: str) -> bool:
        with self.lock:
            if node_id in self.peers:
                del self.peers[node_id]
                return True
            return False
    
    def get_peer(self, node_id: str) -> Optional[Peer]:
        with self.lock:
            return self.peers.get(node_id)
    
    def get_all_peers(self) -> List[Peer]:
        with self.lock:
            # Filter out banned peers
            return [p for p in self.peers.values() if not p.is_banned]
    
    def get_connected_peers(self) -> List[Peer]:
        with self.lock:
            now = time.time()
            return [p for p in self.peers.values() 
                    if not p.is_banned and (now - p.last_seen) < 60]
    
    def update_score(self, node_id: str, reason: str):
        """Update peer score based on behavior"""
        with self.lock:
            peer = self.peers.get(node_id)
            if not peer:
                return
            
            delta = self.score_weights.get(reason, 0)
            peer.score += delta
            
            # Check for ban
            if peer.score <= self.BAN_THRESHOLD and not peer.is_banned:
                self._ban_peer(node_id, reason)
    
    def update_latency(self, node_id: str, latency: float):
        with self.lock:
            peer = self.peers.get(node_id)
            if peer:
                peer.latency = latency
    
    def update_head(self, node_id: str, head_hash: str, head_height: int):
        with self.lock:
            peer = self.peers.get(node_id)
            if peer:
                peer.head_hash = head_hash
                peer.head_height = head_height
                peer.last_seen = time.time()
    
    def update_last_ping(self, node_id: str):
        with self.lock:
            peer = self.peers.get(node_id)
            if peer:
                peer.last_ping = time.time()
    
    def check_rate_limit(self, node_id: str, msg_type: str) -> bool:
        """Check if peer is rate limited"""
        with self.lock:
            peer = self.peers.get(node_id)
            if not peer:
                return False
            
            now = time.time()
            if now - peer.last_reset > 1:  # Reset per second
                peer.msg_count = 0
                peer.last_reset = now
            
            peer.msg_count += 1
            
            # Rate limits
            MAX_MSGS_PER_SEC = 100
            MAX_BLOCK_REQUESTS = 10
            MAX_TX_REQUESTS = 50
            
            if peer.msg_count > MAX_MSGS_PER_SEC:
                self.update_score(node_id, "spam")
                return False
            
            if msg_type == "get_block":
                peer.block_requests += 1
                if peer.block_requests > MAX_BLOCK_REQUESTS:
                    self.update_score(node_id, "spam")
                    return False
            
            if msg_type == "get_tx":
                peer.tx_requests += 1
                if peer.tx_requests > MAX_TX_REQUESTS:
                    self.update_score(node_id, "spam")
                    return False
            
            return True
    
    def _ban_peer(self, node_id: str, reason: str):
        """Ban a peer for malicious behavior"""
        peer = self.peers.get(node_id)
        if peer:
            peer.is_banned = True
            peer.ban_reason = reason
            peer.ban_until = time.time() + self.BAN_DURATION
            self.banned_ips.add(peer.ip)
            print(f"🚫 Banned peer {node_id}: {reason}")
    
    def _is_ip_banned(self, ip: str) -> bool:
        """Check if IP is currently banned"""
        for peer in self.peers.values():
            if peer.ip == ip and peer.is_banned and peer.ban_until > time.time():
                return True
        return ip in self.banned_ips
    
    def _remove_lowest_scoring(self):
        """Remove the lowest scoring peer to make room"""
        if not self.peers:
            return
        lowest = min(self.peers.values(), key=lambda p: p.score)
        del self.peers[lowest.node_id]
    
    def get_best_peers(self, limit: int = 10) -> List[Peer]:
        """Get peers with highest score and height"""
        with self.lock:
            connected = self.get_connected_peers()
            sorted_peers = sorted(connected, key=lambda p: (-p.score, -p.head_height))
            return sorted_peers[:limit]
    
    def get_peer_count(self) -> int:
        with self.lock:
            return len([p for p in self.peers.values() if not p.is_banned])
    
    def get_stats(self) -> dict:
        with self.lock:
            return {
                "total_peers": len(self.peers),
                "connected_peers": len(self.get_connected_peers()),
                "banned_peers": sum(1 for p in self.peers.values() if p.is_banned),
                "max_peers": self.max_peers
            }
