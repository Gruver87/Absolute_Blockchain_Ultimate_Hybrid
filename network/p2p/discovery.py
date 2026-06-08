# network/p2p/discovery.py
"""
Peer discovery with bootstrap nodes
"""

import time
import random
from typing import List, Set, Optional


class Discovery:
    """Peer discovery using bootstrap nodes"""
    
    # Default bootstrap nodes
    DEFAULT_BOOTSTRAP = [
        "bootstrap.absolutechain.io:30303"
    ]
    
    def __init__(self, peer_manager, p2p_server):
        self.peer_manager = peer_manager
        self.p2p_server = p2p_server
        self.bootstrap_nodes: List[str] = []
        self.discovered_peers: Set[str] = set()
    
    def add_bootstrap_node(self, address: str):
        """Add bootstrap node address"""
        self.bootstrap_nodes.append(address)
    
    def add_default_bootstrap(self):
        """Add default bootstrap nodes"""
        for node in self.DEFAULT_BOOTSTRAP:
            self.bootstrap_nodes.append(node)
    
    def discover(self):
        """Start peer discovery"""
        discovered = []
        
        for bootstrap in self.bootstrap_nodes:
            peers = self._query_bootstrap(bootstrap)
            discovered.extend(peers)
        
        # Add discovered peers
        for peer in discovered:
            if peer not in self.discovered_peers:
                self.discovered_peers.add(peer)
                # Attempt to connect
                self._connect_to_peer(peer)
        
        return len(discovered)
    
    def _query_bootstrap(self, bootstrap_addr: str) -> List[str]:
        """Query bootstrap node for peer list"""
        # In real implementation, would send discovery request
        # For now, return empty
        return []
    
    def _connect_to_peer(self, peer_addr: str):
        """Attempt connection to discovered peer"""
        # Parse address: ip:port
        parts = peer_addr.split(":")
        if len(parts) == 2:
            ip, port = parts[0], int(parts[1])
            # Would initiate connection here
            pass
    
    def get_random_peers(self, count: int = 5) -> List:
        """Get random connected peers"""
        peers = self.peer_manager.get_connected_peers()
        if len(peers) <= count:
            return peers
        return random.sample(peers, count)
    
    def get_bootstrap_count(self) -> int:
        return len(self.bootstrap_nodes)
