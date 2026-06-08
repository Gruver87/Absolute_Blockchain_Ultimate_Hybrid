# network/p2p/network.py - COMPLETE P2P NETWORK
import socket
import threading
import json
import time
import hashlib
import random
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque

@dataclass
class Peer:
    address: str
    port: int
    node_id: str
    last_seen: float
    height: int = 0
    version: str = "v55"
    latency: float = 0
    connected: bool = False
    score: int = 100  # Reputation score

class P2PNetwork:
    """Complete P2P network with discovery, handshake, and sync"""
    
    def __init__(self, host="0.0.0.0", port=4567, node=None, node_id=None):
        self.host = host
        self.port = port
        self.node = node
        self.node_id = node_id or hashlib.sha256(f"{host}:{port}".encode()).hexdigest()[:16]
        self.peers: Dict[str, Peer] = {}
        self.peers_lock = threading.Lock()
        self.running = False
        self.server_socket = None
        self.message_handlers = {}
        self.banned_peers: Set[str] = set()
        self.message_queue = deque()
        
        # Bootstrap nodes (hardcoded for initial discovery)
        self.bootstrap_nodes = [
            ("127.0.0.1", 4567),
            ("127.0.0.1", 4568),
            ("127.0.0.1", 4569),
        ]
        
        self._register_handlers()
    
    def _register_handlers(self):
        """Register message handlers"""
        self.message_handlers = {
            "handshake": self._handle_handshake,
            "ping": self._handle_ping,
            "pong": self._handle_pong,
            "get_peers": self._handle_get_peers,
            "peers": self._handle_peers,
            "new_block": self._handle_new_block,
            "get_blocks": self._handle_get_blocks,
            "blocks": self._handle_blocks,
            "new_transaction": self._handle_new_transaction,
            "get_transactions": self._handle_get_transactions,
            "transactions": self._handle_transactions,
            "get_status": self._handle_get_status,
            "status": self._handle_status,
        }
    
    def start(self):
        """Start P2P server"""
        self.running = True
        
        # Start server socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(50)
        
        print(f"🌐 P2P Network running on {self.host}:{self.port}")
        print(f"   Node ID: {self.node_id}")
        
        # Start listener thread
        listener = threading.Thread(target=self._listen, daemon=True)
        listener.start()
        
        # Start peer discovery thread
        discovery = threading.Thread(target=self._discovery_loop, daemon=True)
        discovery.start()
        
        # Start message processor thread
        processor = threading.Thread(target=self._process_messages, daemon=True)
        processor.start()
        
        # Connect to bootstrap nodes
        self._connect_to_bootstrap()
    
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
            # Perform handshake first
            handshake_data = json.dumps({
                "type": "handshake",
                "node_id": self.node_id,
                "version": "v55",
                "height": self.node.blockchain.get_height() if self.node else 0,
                "timestamp": time.time()
            })
            client.send(handshake_data.encode())
            
            # Receive handshake response
            data = client.recv(4096).decode()
            if data:
                message = json.loads(data)
                if message.get("type") == "handshake":
                    peer_id = message.get("node_id")
                    peer_addr = f"{addr[0]}:{message.get('port', self.port)}"
                    
                    with self.peers_lock:
                        self.peers[peer_addr] = Peer(
                            address=addr[0],
                            port=message.get("port", self.port),
                            node_id=peer_id,
                            last_seen=time.time(),
                            height=message.get("height", 0),
                            version=message.get("version", "unknown"),
                            connected=True
                        )
                        print(f"   👥 Peer connected: {peer_addr} (ID: {peer_id[:8]}...)")
            
            # Process messages
            while self.running:
                data = client.recv(4096).decode()
                if not data:
                    break
                message = json.loads(data)
                self.message_queue.append((message, addr[0]))
                
        except Exception as e:
            pass
        finally:
            client.close()
    
    def _discovery_loop(self):
        """Discover new peers periodically"""
        while self.running:
            time.sleep(60)  # Every minute
            
            # Broadcast peer discovery
            self.broadcast({"type": "get_peers"})
            
            # Remove stale peers
            with self.peers_lock:
                now = time.time()
                stale = []
                for addr, peer in self.peers.items():
                    if now - peer.last_seen > 300:  # 5 minutes timeout
                        stale.append(addr)
                for addr in stale:
                    del self.peers[addr]
                    print(f"   👋 Peer removed (timeout): {addr}")
    
    def _connect_to_bootstrap(self):
        """Connect to bootstrap nodes"""
        for host, port in self.bootstrap_nodes:
            if host == self.host and port == self.port:
                continue
            try:
                self.connect_to_peer(host, port)
            except:
                pass
    
    def connect_to_peer(self, host: str, port: int):
        """Connect to a specific peer"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, port))
            
            # Send handshake
            handshake = json.dumps({
                "type": "handshake",
                "node_id": self.node_id,
                "port": self.port,
                "version": "v55",
                "height": self.node.blockchain.get_height() if self.node else 0,
                "timestamp": time.time()
            })
            s.send(handshake.encode())
            
            # Receive handshake response
            data = s.recv(4096).decode()
            if data:
                message = json.loads(data)
                if message.get("type") == "handshake":
                    peer_addr = f"{host}:{port}"
                    with self.peers_lock:
                        if peer_addr not in self.peers:
                            self.peers[peer_addr] = Peer(
                                address=host,
                                port=port,
                                node_id=message.get("node_id"),
                                last_seen=time.time(),
                                height=message.get("height", 0),
                                version=message.get("version", "unknown"),
                                connected=True
                            )
                            print(f"   👥 Connected to peer: {peer_addr}")
            
            s.close()
        except Exception as e:
            pass
    
    def _process_messages(self):
        """Process queued messages"""
        while self.running:
            if self.message_queue:
                message, sender = self.message_queue.popleft()
                msg_type = message.get("type")
                if msg_type in self.message_handlers:
                    self.message_handlers[msg_type](message, sender)
            time.sleep(0.01)
    
    def _handle_handshake(self, message: dict, sender: str):
        """Handle handshake message"""
        peer_id = message.get("node_id")
        peer_addr = f"{sender}:{message.get('port', self.port)}"
        
        with self.peers_lock:
            if peer_addr not in self.peers:
                self.peers[peer_addr] = Peer(
                    address=sender,
                    port=message.get("port", self.port),
                    node_id=peer_id,
                    last_seen=time.time(),
                    height=message.get("height", 0),
                    version=message.get("version", "unknown"),
                    connected=True
                )
    
    def _handle_ping(self, message: dict, sender: str):
        """Handle ping message"""
        self.send_to_peer(sender, {"type": "pong", "timestamp": time.time()})
    
    def _handle_pong(self, message: dict, sender: str):
        """Handle pong message"""
        if sender in self.peers:
            self.peers[sender].last_seen = time.time()
            self.peers[sender].latency = time.time() - message.get("timestamp", time.time())
    
    def _handle_get_peers(self, message: dict, sender: str):
        """Handle get_peers request"""
        peers_list = []
        with self.peers_lock:
            for addr, peer in self.peers.items():
                if addr != sender and not self._is_banned(addr):
                    peers_list.append({
                        "address": peer.address,
                        "port": peer.port,
                        "node_id": peer.node_id
                    })
        self.send_to_peer(sender, {"type": "peers", "peers": peers_list})
    
    def _handle_peers(self, message: dict, sender: str):
        """Handle peers list response"""
        for peer_info in message.get("peers", []):
            peer_addr = f"{peer_info['address']}:{peer_info['port']}"
            if peer_addr not in self.peers and peer_addr != f"{self.host}:{self.port}":
                self.connect_to_peer(peer_info['address'], peer_info['port'])
    
    def _handle_new_block(self, message: dict, sender: str):
        """Handle new block broadcast"""
        block = message.get("block")
        if block and self.node:
            print(f"   📦 Received new block #{block.get('height')} from {sender[:20]}...")
            if self.node.blockchain.add_block(block):
                # Forward to other peers (gossip)
                self.broadcast(message, exclude=[sender])
    
    def _handle_get_blocks(self, message: dict, sender: str):
        """Handle get_blocks request"""
        start = message.get("start", 0)
        end = message.get("end", start + 10)
        blocks = []
        if self.node:
            for h in range(start, min(end, self.node.blockchain.get_height())):
                block = self.node.blockchain.get_block(h)
                if block:
                    blocks.append(block)
        self.send_to_peer(sender, {"type": "blocks", "blocks": blocks})
    
    def _handle_blocks(self, message: dict, sender: str):
        """Handle blocks response"""
        blocks = message.get("blocks", [])
        if blocks and self.node:
            for block in blocks:
                if block.get('height') >= self.node.blockchain.get_height():
                    self.node.blockchain.add_block(block)
                    print(f"   📦 Synced block #{block.get('height')} from {sender[:20]}...")
    
    def _handle_new_transaction(self, message: dict, sender: str):
        """Handle new transaction broadcast"""
        tx = message.get("transaction")
        if tx and self.node and hasattr(self.node, 'mempool'):
            self.node.mempool.add_transaction(tx)
            print(f"   💸 New transaction from {sender[:20]}...")
            self.broadcast(message, exclude=[sender])
    
    def _handle_get_transactions(self, message: dict, sender: str):
        """Handle get_transactions request"""
        if self.node and hasattr(self.node, 'mempool'):
            txs = self.node.mempool.get_sorted_transactions(100)
            self.send_to_peer(sender, {"type": "transactions", "transactions": txs})
    
    def _handle_transactions(self, message: dict, sender: str):
        """Handle transactions response"""
        txs = message.get("transactions", [])
        if txs and self.node and hasattr(self.node, 'mempool'):
            for tx in txs:
                self.node.mempool.add_transaction(tx)
    
    def _handle_get_status(self, message: dict, sender: str):
        """Handle get_status request"""
        if self.node:
            self.send_to_peer(sender, {
                "type": "status",
                "height": self.node.blockchain.get_height(),
                "version": "v55",
                "peers": len(self.peers)
            })
    
    def _handle_status(self, message: dict, sender: str):
        """Handle status response"""
        if sender in self.peers:
            self.peers[sender].height = message.get("height", 0)
    
    def broadcast(self, message: dict, exclude: List[str] = None):
        """Broadcast message to all peers"""
        exclude = exclude or []
        with self.peers_lock:
            for peer_addr in list(self.peers.keys()):
                if peer_addr not in exclude and not self._is_banned(peer_addr):
                    self.send_to_peer(peer_addr, message)
    
    def send_to_peer(self, address: str, message: dict):
        """Send message to specific peer"""
        if self._is_banned(address):
            return
        
        try:
            addr_parts = address.split(':')
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((addr_parts[0], int(addr_parts[1])))
            s.send(json.dumps(message).encode())
            s.close()
        except Exception as e:
            self._penalize_peer(address)
    
    def broadcast_new_block(self, block: dict):
        """Broadcast new block to all peers"""
        self.broadcast({"type": "new_block", "block": block})
    
    def broadcast_new_transaction(self, tx: dict):
        """Broadcast new transaction to all peers"""
        self.broadcast({"type": "new_transaction", "transaction": tx})
    
    def _penalize_peer(self, address: str):
        """Reduce peer score"""
        with self.peers_lock:
            if address in self.peers:
                self.peers[address].score -= 10
                if self.peers[address].score <= 0:
                    self._ban_peer(address)
    
    def _ban_peer(self, address: str):
        """Ban a peer"""
        self.banned_peers.add(address)
        with self.peers_lock:
            if address in self.peers:
                del self.peers[address]
        print(f"   🚫 Peer banned: {address}")
    
    def _is_banned(self, address: str) -> bool:
        """Check if peer is banned"""
        return address in self.banned_peers
    
    def get_peer_count(self) -> int:
        """Get number of connected peers"""
        return len(self.peers)
    
    def get_peers(self) -> List[Dict]:
        """Get list of peers"""
        with self.peers_lock:
            return [
                {
                    "address": peer.address,
                    "port": peer.port,
                    "node_id": peer.node_id,
                    "height": peer.height,
                    "latency": round(peer.latency * 1000, 2),
                    "score": peer.score
                }
                for peer in self.peers.values()
            ]
    
    def sync_from_peers(self):
        """Sync blockchain from peers"""
        if not self.peers:
            return
        
        # Find peer with highest height
        best_peer = None
        best_height = 0
        for peer in self.peers.values():
            if peer.height > best_height:
                best_height = peer.height
                best_peer = peer
        
        if best_peer and best_height > (self.node.blockchain.get_height() if self.node else 0):
            peer_addr = f"{best_peer.address}:{best_peer.port}"
            self.send_to_peer(peer_addr, {
                "type": "get_blocks",
                "start": self.node.blockchain.get_height() if self.node else 0,
                "end": best_height
            })
    
    def stop(self):
        """Stop P2P network"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        print("🌐 P2P Network stopped")
