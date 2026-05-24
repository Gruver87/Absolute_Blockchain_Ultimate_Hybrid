# core/blockchain_network.py
# БЛОКЧЕЙН С P2P СЕТЬЮ И КОНСЕНСУСОМ

import time
import threading
from typing import Dict, List, Optional

from core.blockchain_utxo import BlockchainUTXO
from core.block import Block
from p2p.gossip import P2PNode
from consensus.sync import SyncEngine
from consensus.heaviest_chain import Consensus
from core.utxo_simple import SimpleUTXOSet

class NetworkBlockchain(BlockchainUTXO):
    """Блокчейн с полноценной P2P сетью и консенсусом"""
    
    def __init__(self, data_dir: str = 'data/mainnet', host: str = '0.0.0.0', port: int = 5000):
        super().__init__(data_dir)
        
        # P2P компоненты
        self.p2p = P2PNode(host, port)
        self.sync = SyncEngine(self, self.p2p)
        self.consensus = Consensus(self)
        
        # UTXO для защиты
        self.utxo_set = SimpleUTXOSet()
        self._rebuild_utxo_set()
        
        # Запуск P2P
        self.p2p.start()
        
        # Запуск синхронизации
        self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()
        
        print(f"\n🌐 Network Blockchain инициализирован")
        print(f"   P2P порт: {port}")
        print(f"   Активных пиров: {len(self.p2p.peers)}")
    
    def _rebuild_utxo_set(self):
        """Перестроение UTXO набора из цепочки"""
        for block_data in self.chain:
            if isinstance(block_data, dict):
                self.utxo_set.add_utxos_from_block(block_data)
            else:
                self.utxo_set.add_utxos_from_block(block_data.to_dict())
    
    def _sync_loop(self):
        """Фоновый цикл синхронизации"""
        while True:
            time.sleep(30)
            self.sync.sync()
    
    def has_block(self, block_hash: str) -> bool:
        """Проверка существования блока"""
        for block in self.chain:
            if hasattr(block, 'block_hash'):
                if block.block_hash == block_hash:
                    return True
            elif isinstance(block, dict):
                if block.get('block_hash') == block_hash or block.get('hash') == block_hash:
                    return True
        return False
    
    def get_block_by_hash(self, block_hash: str) -> Optional[Block]:
        """Получение блока по хешу"""
        for block in self.chain:
            if hasattr(block, 'block_hash'):
                if block.block_hash == block_hash:
                    return block
            elif isinstance(block, dict):
                if block.get('block_hash') == block_hash or block.get('hash') == block_hash:
                    return Block.from_dict(block)
        return None
    
    def get_chain(self) -> List:
        """Получение всей цепочки"""
        return self.chain
    
    def add_external_block(self, block_data: dict):
        """Добавление блока из сети"""
        try:
            # Проверка на дубликат
            block_hash = block_data.get('block_hash') or block_data.get('hash')
            if self.has_block(block_hash):
                return
            
            # Создаём блок
            block = Block.from_dict(block_data)
            
            # Проверяем, можно ли добавить
            latest = self.get_latest_block()
            
            if block.previous_hash == latest.block_hash:
                # Простое добавление в цепочку
                self.chain.append(block)
                self.storage.save_block(block)
                self.utxo_set.add_utxos_from_block(block_data)
                print(f"   ✅ Блок #{block.height} добавлен в цепочку")
            elif block.height > latest.height:
                # Возможный форк - проверяем вес
                # Для простоты пока просто игнорируем
                print(f"   ⚠️ Возможный форк: блок #{block.height} (текущая высота {latest.height})")
                
        except Exception as e:
            print(f"   ❌ Ошибка добавления блока: {e}")
    
    def announce_new_block(self, block):
        """Анонс нового блока в сеть"""
        self.sync.announce_new_block(block)
    
    def connect_peer(self, host: str, port: int):
        """Подключение к пиру"""
        self.p2p.connect_peer((host, port))
    
    def get_network_stats(self) -> Dict:
        """Статистика сети"""
        return {
            'p2p_port': self.p2p.port,
            'peers': len(self.p2p.peers),
            'is_running': self.p2p.running,
            'utxo_stats': self.utxo_set.get_stats()
        }
    
    def stop(self):
        """Остановка блокчейна и сети"""
        self.p2p.stop()
        super().close()
