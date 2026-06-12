# nft_core.py - NFT Marketplace для Absolute Blockchain
import json
import time
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

@dataclass
class NFTToken:
    """NFT токен"""
    token_id: str
    name: str
    description: str
    image_url: str
    owner: str
    creator: str
    price: float = 0
    for_sale: bool = False
    created_at: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)

class NFTMarketplace:
    """NFT маркетплейс"""
    
    def __init__(self):
        self.tokens: Dict[str, NFTToken] = {}
        self.collections: Dict[str, List[str]] = {}
        self.lock = threading.RLock()
        self._init_sample_nfts()
    
    def _init_sample_nfts(self):
        """Создание тестовых NFT"""
        samples = [
            ("1", "Absolute Crown", "The ultimate crown of the Absolute Kingdom", "👑", 100),
            ("2", "Quantum Guardian", "Guardian of the quantum realm", "🔮", 200),
            ("3", "Genesis Block", "The first block of eternity", "🔷", 500),
            ("4", "Elemental Master", "Master of all elements", "🌍", 300),
            ("5", "Wisdom Relic", "Ancient artifact of wisdom", "📜", 150),
        ]
        for tid, name, desc, img, price in samples:
            self.mint(f"nft_{tid}", name, desc, img, "0xgenesis", price)
    
    def mint(self, token_id: str, name: str, description: str, image_url: str, 
             creator: str, price: float = 0) -> bool:
        """Создание нового NFT"""
        with self.lock:
            if token_id in self.tokens:
                return False
            self.tokens[token_id] = NFTToken(
                token_id=token_id,
                name=name,
                description=description,
                image_url=image_url,
                owner=creator,
                creator=creator,
                price=price,
                for_sale=price > 0
            )
            return True
    
    def transfer(self, token_id: str, from_addr: str, to_addr: str) -> bool:
        """Перевод NFT"""
        with self.lock:
            if token_id not in self.tokens:
                return False
            token = self.tokens[token_id]
            if token.owner != from_addr:
                return False
            token.owner = to_addr
            token.for_sale = False
            return True
    
    def list_for_sale(self, token_id: str, owner: str, price: float) -> bool:
        """Выставить NFT на продажу"""
        with self.lock:
            if token_id not in self.tokens:
                return False
            token = self.tokens[token_id]
            if token.owner != owner:
                return False
            token.price = price
            token.for_sale = True
            return True
    
    def buy(self, token_id: str, buyer: str) -> Optional[float]:
        """Купить NFT"""
        with self.lock:
            if token_id not in self.tokens:
                return None
            token = self.tokens[token_id]
            if not token.for_sale:
                return None
            price = token.price
            token.owner = buyer
            token.for_sale = False
            return price
    
    def get_tokens_by_owner(self, owner: str) -> List[Dict]:
        """Получить все NFT владельца"""
        with self.lock:
            return [
                self._token_to_dict(t) for t in self.tokens.values()
                if t.owner == owner
            ]
    
    def get_on_sale(self) -> List[Dict]:
        """Получить все NFT в продаже"""
        with self.lock:
            return [
                self._token_to_dict(t) for t in self.tokens.values()
                if t.for_sale
            ]
    
    def get_all_tokens(self) -> List[Dict]:
        """Получить все NFT"""
        with self.lock:
            return [self._token_to_dict(t) for t in self.tokens.values()]
    
    def _token_to_dict(self, token: NFTToken) -> Dict:
        return {
            'token_id': token.token_id,
            'name': token.name,
            'description': token.description,
            'image_url': token.image_url,
            'owner': token.owner,
            'creator': token.creator,
            'price': token.price,
            'for_sale': token.for_sale,
            'created_at': token.created_at
        }
    
    def get_stats(self) -> Dict:
        with self.lock:
            return {
                'total_tokens': len(self.tokens),
                'on_sale': sum(1 for t in self.tokens.values() if t.for_sale),
                'unique_owners': len(set(t.owner for t in self.tokens.values()))
            }

# Глобальный экземпляр
nft_marketplace = NFTMarketplace()
