# network/p2p/peer_manager.py
import socket
import threading
import json
import time
from typing import Dict, List, Set, Optional

class PeerManager:
    """Управление пирами P2P сети"""
    
    def __init__(self, port: int = 5000):
        self.port = port
        self.peers: Set[str] = set()
        self.socket: Optional[socket.socket] = None
        self.running = False
        self.lock = threading.RLock()
    
    def start(self):
        """Запуск P2P сервера"""
        self.running = True
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(('0.0.0.0', self.port))
        self.socket.listen(10)
        
        thread = threading.Thread(target=self._accept_loop, daemon=True)
        thread.start()
        print(f"🌐 P2P Server listening on port {self.port}")
    
    def _accept_loop(self):
        while self.running:
            try:
                client, addr = self.socket.accept()
                self._handle_peer(client, addr)
            except:
                break
    
    def _handle_peer(self, client, addr):
        try:
            data = client.recv(4096).decode()
            if data:
                msg = json.loads(data)
                self.add_peer(addr[0])
                client.send(json.dumps({"status": "ok", "peers": list(self.peers)}).encode())
        except:
            pass
        finally:
            client.close()
    
    def add_peer(self, peer: str):
        with self.lock:
            self.peers.add(peer)
    
    def connect_to_peer(self, host: str, port: int) -> bool:
        """Подключение к другому пиру"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
            sock.send(json.dumps({"type": "handshake", "peer": "self"}).encode())
            response = json.loads(sock.recv(4096).decode())
            self.add_peer(host)
            sock.close()
            return True
        except:
            return False
    
    def broadcast(self, data: Dict):
        """Рассылка данных всем пирам"""
        with self.lock:
            for peer in self.peers:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect((peer, self.port))
                    sock.send(json.dumps(data).encode())
                    sock.close()
                except:
                    pass
    
    def get_peers(self) -> List[str]:
        with self.lock:
            return list(self.peers)
    
    def stop(self):
        self.running = False
        if self.socket:
            self.socket.close()

peer_manager = PeerManager()
