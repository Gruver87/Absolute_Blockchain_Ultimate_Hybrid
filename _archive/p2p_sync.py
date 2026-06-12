# p2p/sync.py
# HEADER-FIRST SYNC И FORK CHOICE (Bitcoin-style)

import time
import threading
from typing import List, Dict, Optional
from p2p.wire import Wire, MSG_GETHEADERS, MSG_HEADERS, MSG_GETDATA, MSG_BLOCK

class SyncManager:
    """Менеджер синхронизации блокчейна"""
    
    def __init__(self, blockchain, p2p_node):
        self.blockchain = blockchain
        self.p2p = p2p_node
        self.running = False
        self.sync_lock = threading.RLock()
        
        print("🔄 Менеджер синхронизации инициализирован")
    
    def start(self):
        """Запуск синхронизации"""
        self.running = True
        sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        sync_thread.start()
        print("✅ Синхронизация запущена")
    
    def _sync_loop(self):
        """Основной цикл синхронизации"""
        while self.running:
            try:
                self._sync_with_peers()
                time.sleep(30)
            except Exception as e:
                pass
    
    def _sync_with_peers(self):
        """Синхронизация с пирами (header-first)"""
        for peer in self.p2p.get_peers():
            self._sync_headers_from_peer(peer)
    
    def _sync_headers_from_peer(self, peer: tuple):
        """Header-first sync: сначала запрашиваем заголовки"""
        current_height = self.blockchain.get_latest_block().height if self.blockchain.chain else 0
        
        # Запрос заголовков
        msg = {"type": MSG_GETHEADERS, "from_height": current_height}
        self.p2p._send_message(peer, msg)
    
    def process_headers(self, headers: List[Dict]):
        """Обработка полученных заголовков"""
        for header in headers:
            if not self.blockchain.has_block(header.get("hash")):
                self._request_block(header.get("hash"))
    
    def _request_block(self, block_hash: str):
        """Запрос полного блока"""
        self.p2p.broadcast({
            "type": MSG_GETDATA,
            "block_hash": block_hash
        })
    
    def chain_weight(self, chain: List[Dict]) -> int:
        """Вычисление веса цепочки (сумма difficulty)"""
        return sum(block.get("difficulty", 1) for block in chain)
    
    def resolve_fork(self, chains: List[List[Dict]]) -> Optional[List[Dict]]:
        """
        Fork choice rule: выбираем цепочку с наибольшим весом
        (Heaviest Chain Rule - как в Bitcoin)
        """
        best_chain = None
        best_weight = 0
        
        for chain in chains:
            weight = self.chain_weight(chain)
            if weight > best_weight:
                best_chain = chain
                best_weight = weight
        
        return best_chain
    
    def reorganize_chain(self, new_chain: List[Dict]):
        """
        Reorg engine: переорганизация цепочки при форке
        """
        with self.sync_lock:
            old_chain = self.blockchain.chain.copy()
            
            # Rollback старых блоков
            for block in reversed(old_chain):
                if hasattr(self.blockchain, 'rollback_block'):
                    self.blockchain.rollback_block(block)
            
            # Apply новых блоков
            for block in new_chain:
                if hasattr(self.blockchain, 'apply_block'):
                    self.blockchain.apply_block(block)
            
            self.blockchain.chain = new_chain
            print(f"🔄 REORG: цепочка переорганизована с {len(old_chain)} на {len(new_chain)} блоков")
    
    def stop(self):
        self.running = False
