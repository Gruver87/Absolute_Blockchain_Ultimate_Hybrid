# modules/nft.py
# NFT МОДУЛЬ С ХРАНЕНИЕМ В ROCKSDB

import json
import os
import time
from typing import Dict, List, Optional

class NFTModule:
    """NFT система с постоянным хранением в RocksDB"""
    
    def __init__(self, storage):
        self.storage = storage
        self.tokens = {}
        self._load_tokens()
        self._init_default_nfts()
        print(f"   ✅ NFT Module загружен: {len(self.tokens)} токенов")
    
    def _load_tokens(self):
        """Загрузка NFT из RocksDB"""
        try:
            for key, value in self.storage.db.items():
                key_str = key.decode() if isinstance(key, bytes) else key
                if key_str.startswith("nft:"):
                    token_id = key_str[4:]
                    nft_data = json.loads(value) if isinstance(value, str) else value
                    if isinstance(nft_data, dict):
                        self.tokens[token_id] = nft_data
        except Exception as e:
            print(f"   ⚠️ Ошибка загрузки NFT: {e}")
    
    def _save_token(self, token_id: str, token_data: Dict):
        """Сохранение NFT в RocksDB"""
        self.storage.db[f"nft:{token_id}"] = json.dumps(token_data, default=str)
        self.tokens[token_id] = token_data
    
    def _init_default_nfts(self):
        """Создание 60 начальных NFT героев (если нет)"""
        if len(self.tokens) >= 60:
            return
        
        for i in range(60):
            token_id = f"hero_{i+1:03d}"
            if token_id in self.tokens:
                continue
            
            nft_data = {
                'token_id': token_id,
                'name': f"Hero #{i+1}",
                'image': f"https://picsum.photos/id/{i+1}/400/400",
                'owner': 'foundation',
                'attributes': {
                    'strength': 50 + i,
                    'intelligence': 40 + i % 60,
                    'agility': 30 + i % 50,
                    'level': 1,
                    'experience': 0
                },
                'created_at': int(time.time())
            }
            self._save_token(token_id, nft_data)
        
        print(f"   ✅ Создано {len(self.tokens)} NFT героев")
    
    def get_stats(self) -> Dict:
        """Статистика NFT системы"""
        owners = {}
        for token in self.tokens.values():
            owner = token.get('owner', 'unknown')
            owners[owner] = owners.get(owner, 0) + 1
        
        return {
            'total_nfts': len(self.tokens),
            'collections': 1,
            'unique_owners': len(owners),
            'total_supply': len(self.tokens)
        }
    
    def get_all_tokens(self) -> List[Dict]:
        """Получение всех NFT токенов"""
        return list(self.tokens.values())
    
    def get_tokens(self) -> List[Dict]:
        """Алиас для get_all_tokens (для совместимости с API)"""
        return self.get_all_tokens()
    
    def get_token(self, token_id: str) -> Optional[Dict]:
        """Получение NFT по ID"""
        return self.tokens.get(token_id)
    
    def mint(self, data: Dict) -> Dict:
        """Создание нового NFT"""
        token_id = f"nft_{int(time.time())}_{len(self.tokens)}"
        nft_data = {
            'token_id': token_id,
            'name': data.get('name', 'New NFT'),
            'owner': data.get('owner', 'foundation'),
            'created_at': int(time.time()),
            'attributes': data.get('attributes', {})
        }
        self._save_token(token_id, nft_data)
        return {'success': True, 'token_id': token_id, 'data': nft_data}
    
    def transfer(self, token_id: str, to_addr: str) -> bool:
        """Перевод NFT другому владельцу"""
        if token_id in self.tokens:
            self.tokens[token_id]['owner'] = to_addr
            self._save_token(token_id, self.tokens[token_id])
            return True
        return False
    
    def get_owner_tokens(self, owner: str) -> List[Dict]:
        """Получение NFT по владельцу"""
        return [t for t in self.tokens.values() if t.get('owner') == owner]
    
    def stop(self):
        """Остановка модуля (сохранение)"""
        # Данные уже сохраняются при каждом изменении
        pass
