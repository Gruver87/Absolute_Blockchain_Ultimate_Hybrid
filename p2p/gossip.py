# p2p/gossip.py
# P2P GOSSIP LAYER - РАСПРОСТРАНЕНИЕ БЛОКОВ ПО СЕТИ

import json
import socket
import threading
import time
from typing import Dict, Set, Callable, Any

class P2PNode:
    """P2P узел с поддержкой блокчейн сообщений"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 5000):
        self.host = host
        self.port = port
        self.peers: Set[tuple] = set()
        self.running = False
        self.handlers: Dict[str, Callable] = {}
        self.known_blocks: Set[str] = set()
        
    def start(self):
        """Запуск P2P узла"""
        self.running = True
        t = threading.Thread(target=self._listen, daemon=True)
        t.start()
        print(f"📡 P2P узел запущен на {self.host}:{self.port}")
    
    def connect_peer(self, peer: tuple):
        """Подключение к пиру"""
        self.peers.add(peer)
        print(f"   ✅ Подключён пир: {peer[0]}:{peer[1]}")
    
    def broadcast(self, msg: dict):
        """Широковещательная рассылка сообщения всем пирам"""
        data = json.dumps(msg, default=str).encode()
        for peer in list(self.peers):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect((peer[0], peer[1]))
                s.send(data)
                s.close()
            except:
                pass
    
    def send_to_peer(self, peer: tuple, msg: dict):
        """Отправка сообщения конкретному пиру"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((peer[0], peer[1]))
            s.send(json.dumps(msg, default=str).encode())
            s.close()
        except:
            pass
    
    def _listen(self):
        """Слушатель входящих соединений"""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.host, self.port))
        s.listen(50)
        
        while self.running:
            try:
                conn, addr = s.accept()
                data = conn.recv(100000).decode()
                conn.close()
                
                if not data:
                    continue
                
                msg = json.loads(data)
                self._handle(msg, addr[0])
            except:
                pass
    
    def _handle(self, msg: dict, peer_ip: str):
        """Обработка входящего сообщения"""
        msg_type = msg.get("type")
        
        if msg_type in self.handlers:
            self.handlers[msg_type](msg, peer_ip)
    
    def announce_new_block(self, block: dict):
        """Анонс нового блока в сеть"""
        block_hash = block.get("block_hash") or block.get("hash")
        if block_hash and block_hash not in self.known_blocks:
            self.known_blocks.add(block_hash)
            self.broadcast({
                "type": "block",
                "block": block,
                "timestamp": time.time()
            })
    
    def stop(self):
        """Остановка узла"""
        self.running = False

# Тест
if __name__ == "__main__":
    node = P2PNode(port=5000)
    node.start()
    print("\n✅ P2P Gossip Layer готов")
