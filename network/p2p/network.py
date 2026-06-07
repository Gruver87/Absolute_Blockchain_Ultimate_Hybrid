# network/p2p/network.py - Complete P2P network
import socket
import threading
import json
import time
import hashlib
from typing import Dict, List, Set, Optional
from dataclasses import dataclass
from collections import deque

@dataclass
class Peer:
    address: str
    port: int
    last_seen: float
    height: int = 0
    version: str = "v54"

class P2PNetwork:
    """Peer-to-peer network for blockchain nodes"""
    
    def __init__(self, host="0.0.0.0", port=4567, node=None):
        self.host = host
        self.port = port
        self.node = node
        self.peers: Dict[str, Peer] = {}
        self.peers_lock = threading.Lock()
        self.running = False
        self.server_socket = None
        
    def start(self):
        """Start P2P server"""
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(10)
        
        print(f"🌐 P2P Network running on {self.host}:{self.port}")
        
        # Start listener thread
        listener = threading.Thread(target=self._listen, daemon=True)
        listener.start()
        
        # Start peer discovery
        discovery = threading.Thread(target=self._discovery_loop, daemon=True)
        discovery.start()
    
    def _listen(self):
        """Listen for incoming connections"""
        while self.running:
            try:
                client, addr = self.server_socket.accept()
                handler = threading.Thread(target=self._handle_peer, args=(client, addr))
                handler.daemon = True
                handler.start()
            except:
                pass
    
    def _handle_peer(self, client, addr):
        """Handle peer connection"""
        try:
            data = client.recv(4096).decode()
            if data:
                message = json.loads(data)
                self._process_message(message, addr[0])
            client.close()
        except:
            pass
    
    def _process_message(self, message: dict, sender: str):
        """Process incoming message"""
        msg_type = message.get('type')
        
        if msg_type == 'ping':
            response = {'type': 'pong', 'height': self.node.blockchain.get_height()}
            self.send_to_peer(sender, response)
            
        elif msg_type == 'pong':
            if sender in self.peers:
                self.peers[sender].last_seen = time.time()
                self.peers[sender].height = message.get('height', 0)
        
        elif msg_type == 'new_block':
            block = message.get('block')
            if block and self.node:
                self.node.blockchain.add_block(block)
                print(f"   📦 Received block #{block.get('height')} from {sender}")
        
        elif msg_type == 'get_blocks':
            start = message.get('start', 0)
            end = message.get('end', start + 10)
            blocks = []
            for h in range(start, min(end, self.node.blockchain.get_height())):
                block = self.node.blockchain.get_block(h)
                if block:
                    blocks.append(block)
            response = {'type': 'blocks', 'blocks': blocks}
            self.send_to_peer(sender, response)
    
    def _discovery_loop(self):
        """Discover new peers"""
        while self.running:
            for peer_addr in list(self.peers.keys()):
                try:
                    self.send_to_peer(peer_addr, {'type': 'ping'})
                except:
                    with self.peers_lock:
                        if peer_addr in self.peers:
                            del self.peers[peer_addr]
            
            time.sleep(30)
    
    def add_peer(self, address: str, port: int):
        """Add peer manually"""
        peer_key = f"{address}:{port}"
        with self.peers_lock:
            if peer_key not in self.peers:
                self.peers[peer_key] = Peer(address=address, port=port, last_seen=time.time())
                print(f"   👥 New peer added: {peer_key}")
    
    def broadcast(self, message: dict):
        """Broadcast message to all peers"""
        for peer in list(self.peers.keys()):
            try:
                self.send_to_peer(peer, message)
            except:
                pass
    
    def send_to_peer(self, address: str, message: dict):
        """Send message to specific peer"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            addr_parts = address.split(':')
            s.connect((addr_parts[0], int(addr_parts[1])))
            s.send(json.dumps(message).encode())
            s.close()
        except:
            pass
    
    def broadcast_new_block(self, block: dict):
        """Broadcast new block to all peers"""
        self.broadcast({'type': 'new_block', 'block': block})
    
    def get_peer_count(self) -> int:
        """Get number of connected peers"""
        return len(self.peers)
    
    def get_peers(self) -> List[str]:
        """Get list of peer addresses"""
        return list(self.peers.keys())
    
    def stop(self):
        """Stop P2P network"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
