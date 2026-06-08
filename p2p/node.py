# p2p/node.py
# НАСТОЯЩИЙ P2P УЗЕЛ - GOSSIP PROTOCOL

import socket
import threading
import time
import json
from typing import Set, Dict, List, Optional
from p2p.wire import Wire, MSG_INV, MSG_GETDATA, MSG_BLOCK, MSG_HEADERS, MSG_TX, MSG_PING, MSG_PONG, MSG_GETHEADERS

class P2PNode:
    """Реальный P2P узел с gossip протоколом (Bitcoin-style)"""
    
    def __init__(self, host: str = '0.0.0.0', port: int = 5000, blockchain=None):
        self.host = host
        self.port = port
        self.blockchain = blockchain
        self.peers: Set[tuple] = set()
        self.running = False
        self.socket = None
        self.known_inventory: Set[str] = set()  # INV фильтрация
        self.pending_blocks: Dict[str, Dict] = {}  # ожидаемые блоки
        
        print(f"📡 P2P узел инициализирован: {host}:{port}")
    
    def start(self):
        """Запуск P2P узла"""
        self.running = True
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen(10)
        
        # Запуск слушающего потока
        listener = threading.Thread(target=self._listen_loop, daemon=True)
        listener.start()
        
        # Запуск gossip рассылки
        gossip = threading.Thread(target=self._gossip_loop, daemon=True)
        gossip.start()
        
        print(f"✅ P2P узел запущен на {self.host}:{self.port}")
        print(f"   Активных пиров: {len(self.peers)}")
    
    def _listen_loop(self):
        """Основной цикл приёма соединений"""
        while self.running:
            try:
                client, addr = self.socket.accept()
                self.peers.add(addr)
                threading.Thread(target=self._handle_client, args=(client, addr), daemon=True).start()
            except:
                pass
    
    def _handle_client(self, client: socket.socket, addr: tuple):
        """Обработка входящего соединения"""
        try:
            client.settimeout(30)
            data = client.recv(65536)  # 64KB max
            if data:
                msg = Wire.unpack(data)
                self._process_message(msg, addr)
            client.close()
        except Exception as e:
            pass
    
    def _process_message(self, msg: Dict, sender: tuple):
        """Обработка входящего сообщения"""
        msg_type = msg.get("type")
        
        if msg_type == MSG_PING:
            self._send_message(sender, {"type": MSG_PONG})
        
        elif msg_type == MSG_PONG:
            pass  # соединение живо
        
        elif msg_type == MSG_INV:
            self._handle_inv(msg)
        
        elif msg_type == MSG_GETDATA:
            self._handle_getdata(msg)
        
        elif msg_type == MSG_BLOCK:
            self._handle_block(msg)
        
        elif msg_type == MSG_TX:
            self._handle_tx(msg)
        
        elif msg_type == MSG_GETHEADERS:
            self._handle_getheaders(msg, sender)
    
    def _send_message(self, target: tuple, msg: Dict):
        """Отправка сообщения конкретному пиру"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(target)
            sock.send(Wire.pack(msg))
            sock.close()
        except:
            pass
    
    def broadcast(self, msg: Dict):
        """Gossip рассылка всем пирам"""
        data = Wire.pack(msg)
        for peer in list(self.peers):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect(peer)
                sock.send(data)
                sock.close()
            except:
                self.peers.discard(peer)
    
    # ========== INV / GETDATA / BLOCK ==========
    
    def announce_block(self, block: Dict):
        """Объявление о новом блоке (INV)"""
        block_hash = block.get("block_hash") or block.get("hash")
        if block_hash and block_hash not in self.known_inventory:
            self.known_inventory.add(block_hash)
            self.broadcast({
                "type": MSG_INV,
                "block_hash": block_hash,
                "height": block.get("height", 0)
            })
    
    def announce_tx(self, tx_hash: str):
        """Объявление о новой транзакции"""
        if tx_hash not in self.known_inventory:
            self.known_inventory.add(tx_hash)
            self.broadcast({
                "type": MSG_INV,
                "tx_hash": tx_hash
            })
    
    def _handle_inv(self, msg: Dict):
        """Обработка INV (у кого-то есть блок/транзакция)"""
        block_hash = msg.get("block_hash")
        tx_hash = msg.get("tx_hash")
        
        if block_hash:
            if self.blockchain and not self.blockchain.has_block(block_hash):
                self.broadcast({
                    "type": MSG_GETDATA,
                    "block_hash": block_hash
                })
        
        elif tx_hash:
            self.broadcast({
                "type": MSG_GETDATA,
                "tx_hash": tx_hash
            })
    
    def _handle_getdata(self, msg: Dict):
        """Обработка GETDATA (запрос блока/транзакции)"""
        block_hash = msg.get("block_hash")
        tx_hash = msg.get("tx_hash")
        
        if block_hash and self.blockchain:
            block = self.blockchain.get_block_by_hash(block_hash)
            if block:
                self.broadcast({
                    "type": MSG_BLOCK,
                    "block": block.to_dict() if hasattr(block, 'to_dict') else block
                })
    
    def _handle_block(self, msg: Dict):
        """Обработка полученного блока"""
        block_data = msg.get("block")
        if block_data and self.blockchain:
            # Передаём блок в блокчейн для обработки
            if hasattr(self.blockchain, 'process_incoming_block'):
                self.blockchain.process_incoming_block(block_data)
    
    def _handle_tx(self, msg: Dict):
        """Обработка полученной транзакции"""
        tx_data = msg.get("tx")
        if tx_data and self.blockchain:
            if hasattr(self.blockchain, 'add_transaction'):
                self.blockchain.add_transaction(tx_data)
    
    def _handle_getheaders(self, msg: Dict, sender: tuple):
        """Обработка запроса заголовков (header-first sync)"""
        if self.blockchain:
            headers = self.blockchain.get_block_headers(msg.get("from_height", 0))
            self._send_message(sender, {
                "type": MSG_HEADERS,
                "headers": headers
            })
    
    def _gossip_loop(self):
        """Периодическая рассылка (keep-alive)"""
        while self.running:
            time.sleep(30)
            self.broadcast({"type": MSG_PING})
    
    def add_peer(self, host: str, port: int):
        """Добавление нового пира"""
        self.peers.add((host, port))
        print(f"   ✅ Добавлен пир: {host}:{port}")
    
    def get_peers(self) -> List[tuple]:
        """Получение списка пиров"""
        return list(self.peers)
    
    def stop(self):
        """Остановка P2P узла"""
        self.running = False
        if self.socket:
            self.socket.close()
        print("📡 P2P узел остановлен")

# Тест
if __name__ == "__main__":
    print("=" * 60)
    print("P2P Node - Тест")
    print("=" * 60)
    
    node = P2PNode(port=5000)
    node.start()
    
    print("\n✅ P2P узел готов к работе!")
    print("   Нажмите Ctrl+C для остановки\n")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        node.stop()
