# consensus/sync.py
# BLOCK SYNC ENGINE - СИНХРОНИЗАЦИЯ ЦЕПОЧКИ

import time
import threading
from typing import Dict, List, Optional

class SyncEngine:
    """Движок синхронизации блокчейна"""
    
    def __init__(self, blockchain, p2p):
        self.bc = blockchain
        self.p2p = p2p
        
        # Регистрируем обработчики
        self.p2p.handlers["block"] = self.on_block
        self.p2p.handlers["get_headers"] = self.on_get_headers
        self.p2p.handlers["headers"] = self.on_headers
        self.p2p.handlers["get_block"] = self.on_get_block
        
        self.syncing = False
        print("🔄 Sync Engine инициализирован")
    
    # 📦 receive block
    def on_block(self, msg: dict, peer: str):
        """Обработка полученного блока"""
        block = msg.get("block")
        
        if not block:
            return
        
        if not self.validate_block(block):
            print(f"   ⚠️ Невалидный блок от {peer}")
            return
        
        block_hash = block.get("block_hash") or block.get("hash")
        block_height = block.get("height")
        
        # Проверяем, есть ли уже такой блок
        if self.bc.has_block(block_hash):
            return
        
        local_height = self.bc.get_latest_block().height if hasattr(self.bc.get_latest_block(), 'height') else self.bc.get_latest_block().get('height', 0)
        
        # Принимаем только более высокие блоки
        if block_height > local_height:
            print(f"📥 Получен блок #{block_height} от {peer}")
            self.bc.add_external_block(block)
        elif block_height == local_height + 1:
            # Новый блок, продолжаем цепочку
            print(f"📥 Новый блок #{block_height} от {peer}")
            self.bc.add_external_block(block)
    
    # 📡 запрос заголовков
    def sync(self):
        """Запуск синхронизации"""
        if self.syncing:
            return
        
        self.syncing = True
        print("\n🔄 Запуск синхронизации...")
        self.p2p.broadcast({"type": "get_headers"})
        
        # Таймер для сброса флага
        threading.Timer(30, lambda: setattr(self, 'syncing', False)).start()
    
    # 📜 отправка заголовков
    def on_get_headers(self, msg: dict, peer: str):
        """Отправка заголовков запросившему пиру"""
        chain = self.bc.get_chain()
        headers = []
        
        for block in chain:
            if hasattr(block, 'to_dict'):
                b = block.to_dict()
            else:
                b = block
            
            headers.append({
                "height": b.get("height"),
                "hash": b.get("block_hash") or b.get("hash"),
                "prev": b.get("previous_hash"),
                "merkle": b.get("merkle_root")
            })
        
        self.p2p.send_to_peer((peer, self.p2p.port), {
            "type": "headers",
            "headers": headers
        })
    
    # 📥 получение заголовков
    def on_headers(self, msg: dict, peer: str):
        """Обработка полученных заголовков"""
        headers = msg.get("headers", [])
        local_height = self.bc.get_latest_block().height if hasattr(self.bc.get_latest_block(), 'height') else self.bc.get_latest_block().get('height', 0)
        
        for header in headers:
            if header.get("height", 0) > local_height:
                self.request_block(header.get("hash"), peer)
    
    def on_get_block(self, msg: dict, peer: str):
        """Отправка запрошенного блока"""
        block_hash = msg.get("hash")
        block = self.bc.get_block_by_hash(block_hash)
        
        if block:
            self.p2p.send_to_peer((peer, self.p2p.port), {
                "type": "block",
                "block": block.to_dict() if hasattr(block, 'to_dict') else block
            })
    
    def request_block(self, block_hash: str, peer: str):
        """Запрос блока у пира"""
        self.p2p.send_to_peer((peer, self.p2p.port), {
            "type": "get_block",
            "hash": block_hash
        })
    
    def validate_block(self, block: dict) -> bool:
        """Минимальная валидация блока"""
        required_fields = ["height", "block_hash", "previous_hash", "merkle_root"]
        for field in required_fields:
            if field not in block:
                return False
        return True
    
    def announce_new_block(self, block):
        """Анонс нового блока в сеть"""
        block_data = block.to_dict() if hasattr(block, 'to_dict') else block
        self.p2p.announce_new_block(block_data)
    
    def stop(self):
        """Остановка синхронизации"""
        self.syncing = False

# Тест
if __name__ == "__main__":
    print("✅ Sync Engine готов")
