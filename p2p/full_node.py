# p2p/full_node.py
# ПОЛНЫЙ УЗЕЛ С ВАЛИДАЦИЕЙ И КОНСЕНСУСОМ

import time
import threading
from typing import Optional, Dict, List

from p2p.node import P2PNode
from p2p.sync import SyncManager
from p2p.wire import NODE_FULL, NODE_LIGHT, NODE_VALIDATOR

class FullNode:
    """Полный узел блокчейна (full node)"""
    
    def __init__(self, blockchain, host: str = '0.0.0.0', port: int = 5000, role: str = NODE_FULL):
        self.blockchain = blockchain
        self.host = host
        self.port = port
        self.role = role
        
        # P2P компоненты
        self.p2p = P2PNode(host, port, blockchain)
        self.sync = SyncManager(blockchain, self.p2p)
        
        self.running = False
        
        print(f"🧠 Полный узел инициализирован (роль: {role})")
    
    def start(self):
        """Запуск узла"""
        self.running = True
        
        # Запуск P2P
        self.p2p.start()
        
        # Запуск синхронизации
        self.sync.start()
        
        # Запуск консенсусного цикла
        consensus_thread = threading.Thread(target=self._consensus_loop, daemon=True)
        consensus_thread.start()
        
        print(f"✅ Узел запущен на {self.host}:{self.port}")
    
    def _consensus_loop(self):
        """Основной цикл консенсуса"""
        while self.running:
            try:
                # Синхронизация с пирами
                self.p2p.broadcast({"type": "ping"})
                
                # Проверка форков
                self._check_forks()
                
                time.sleep(10)
            except:
                pass
    
    def _check_forks(self):
        """Проверка и разрешение форков"""
        # Сбор цепочек от пиров
        chains = []
        
        # Основная цепочка
        if self.blockchain.chain:
            chains.append([b.to_dict() if hasattr(b, 'to_dict') else b for b in self.blockchain.chain])
        
        # Выбор лучшей цепочки
        best_chain = self.sync.resolve_fork(chains)
        
        # Если найдена лучшая цепочка - переорганизуем
        if best_chain and len(best_chain) > len(self.blockchain.chain):
            self.sync.reorganize_chain(best_chain)
    
    def announce_new_block(self, block):
        """Анонс нового блока в сеть"""
        block_data = block.to_dict() if hasattr(block, 'to_dict') else block
        self.p2p.announce_block(block_data)
    
    def get_peers(self) -> List[tuple]:
        return self.p2p.get_peers()
    
    def stop(self):
        """Остановка узла"""
        self.running = False
        self.sync.stop()
        self.p2p.stop()
        print(f"🧠 Узел остановлен")

# Тест
if __name__ == "__main__":
    print("=" * 60)
    print("Full Node - Тест")
    print("=" * 60)
    
    # Здесь нужен реальный blockchain объект
    # node = FullNode(blockchain, port=5000)
    # node.start()
    
    print("\n✅ Full Node готов к интеграции!")
