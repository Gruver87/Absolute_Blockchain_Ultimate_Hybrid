#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NFT CORE - ПОЛНАЯ NFT СИСТЕМА ДЛЯ ABSOLUTE BLOCKCHAIN
"""

import time
import json
import hashlib
import secrets
import threading
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

# Типы NFT с характеристиками
NFT_STATS = {
    'dragon': {'strength': 85, 'intelligence': 70, 'charisma': 80, 'icon': '🐉', 'rarity': 'mythic', 'name': 'Дракон'},
    'lion': {'strength': 90, 'intelligence': 65, 'charisma': 75, 'icon': '🦁', 'rarity': 'legendary', 'name': 'Лев'},
    'wolf': {'strength': 75, 'intelligence': 85, 'charisma': 70, 'icon': '🐺', 'rarity': 'epic', 'name': 'Волк'},
    'phoenix': {'strength': 80, 'intelligence': 90, 'charisma': 85, 'icon': '🐦‍🔥', 'rarity': 'mythic', 'name': 'Феникс'},
    'samurai': {'strength': 88, 'intelligence': 75, 'charisma': 72, 'icon': '⚔️', 'rarity': 'legendary', 'name': 'Самурай'},
    'elf': {'strength': 70, 'intelligence': 88, 'charisma': 82, 'icon': '🏹', 'rarity': 'epic', 'name': 'Эльф'},
    'knight': {'strength': 85, 'intelligence': 70, 'charisma': 75, 'icon': '🛡️', 'rarity': 'legendary', 'name': 'Рыцарь'},
    'mage': {'strength': 60, 'intelligence': 95, 'charisma': 85, 'icon': '🔮', 'rarity': 'epic', 'name': 'Маг'},
    'angel': {'strength': 82, 'intelligence': 80, 'charisma': 90, 'icon': '👼', 'rarity': 'mythic', 'name': 'Ангел'},
    'ninja': {'strength': 78, 'intelligence': 85, 'charisma': 70, 'icon': '🥷', 'rarity': 'epic', 'name': 'Ниндзя'}
}

# ========== NFT STANDARD (ERC-721) ==========

class NFTStandard:
    def __init__(self):
        self.tokens: Dict[str, Dict] = {}
        self.owners: Dict[str, str] = {}
        self.balances: Dict[str, int] = defaultdict(int)
        self.total_supply = 0
        self.total_transfers = 0
        self.lock = threading.RLock()
        self.next_id = 1
        print("NFT Standard (ERC-721) инициализирован")
    
    def _generate_token_id(self) -> str:
        token_id = f"NFT_{int(time.time())}_{self.next_id}_{secrets.token_hex(4)}"
        self.next_id += 1
        return token_id
    
    def mint(self, to_addr: str, nft_type: str, name: str = None, extra_stats: Dict = None) -> str:
        with self.lock:
            token_id = self._generate_token_id()
            base_stats = NFT_STATS.get(nft_type, NFT_STATS['dragon']).copy()
            
            stats = {
                'strength': base_stats.get('strength', 50),
                'intelligence': base_stats.get('intelligence', 50),
                'charisma': base_stats.get('charisma', 50)
            }
            
            if extra_stats:
                stats['strength'] += extra_stats.get('strength', 0)
                stats['intelligence'] += extra_stats.get('intelligence', 0)
                stats['charisma'] += extra_stats.get('charisma', 0)
            
            for key in stats:
                stats[key] = max(20, min(120, stats[key]))
            
            total_power = stats['strength'] + stats['intelligence'] + stats['charisma']
            
            if total_power > 240:
                rarity = 'mythic'
            elif total_power > 210:
                rarity = 'legendary'
            elif total_power > 180:
                rarity = 'epic'
            else:
                rarity = 'rare'
            
            icon = base_stats.get('icon', '🦋')
            display_name = name or f"{icon} {base_stats.get('name', nft_type).capitalize()} #{self.total_supply + 1}"
            
            token = {
                'id': token_id,
                'name': display_name,
                'type': nft_type,
                'icon': icon,
                'owner': to_addr,
                'created': time.time(),
                'stats': stats,
                'total_power': total_power,
                'rarity': rarity,
                'generation': extra_stats.get('generation', 1) if extra_stats else 1,
                'parents': extra_stats.get('parents', []) if extra_stats else [],
                'price': self._calculate_price(rarity, total_power)
            }
            
            self.tokens[token_id] = token
            self.owners[token_id] = to_addr
            self.balances[to_addr] += 1
            self.total_supply += 1
            
            print(f"NFT создан: {display_name} [{rarity}]")
            return token_id
    
    def _calculate_price(self, rarity: str, power: int) -> int:
        prices = {'mythic': 5000, 'legendary': 2500, 'epic': 1000, 'rare': 400}
        base = prices.get(rarity, 500)
        return base + (power // 10) * 10
    
    def transfer(self, from_addr: str, to_addr: str, token_id: str) -> bool:
        with self.lock:
            if token_id not in self.owners:
                return False
            if self.owners[token_id] != from_addr:
                return False
            
            self.owners[token_id] = to_addr
            self.tokens[token_id]['owner'] = to_addr
            self.balances[from_addr] -= 1
            self.balances[to_addr] += 1
            self.total_transfers += 1
            return True
    
    def owner_of(self, token_id: str) -> Optional[str]:
        return self.owners.get(token_id)
    
    def balance_of(self, owner: str) -> int:
        return self.balances.get(owner, 0)
    
    def get_token(self, token_id: str) -> Optional[Dict]:
        return self.tokens.get(token_id)
    
    def get_tokens_by_owner(self, owner: str) -> List[Dict]:
        return [t for t in self.tokens.values() if t['owner'] == owner]
    
    def get_all_tokens(self) -> List[Dict]:
        return list(self.tokens.values())
    
    def get_stats(self) -> Dict:
        with self.lock:
            unique_owners = len(set(self.owners.values()))
            by_rarity = defaultdict(int)
            by_type = defaultdict(int)
            for token in self.tokens.values():
                by_rarity[token['rarity']] += 1
                by_type[token['type']] += 1
            return {
                'total_supply': self.total_supply,
                'total_transfers': self.total_transfers,
                'unique_owners': unique_owners,
                'by_rarity': dict(by_rarity),
                'by_type': dict(by_type)
            }

# ========== NFT MARKETPLACE ==========

class NFTMarketplace:
    def __init__(self, nft: NFTStandard):
        self.nft = nft
        self.listings: Dict[str, Dict] = {}
        self.sales: List[Dict] = []
        self.platform_fee = 0.02
        self.lock = threading.RLock()
        self.next_id = 1
        print(f"NFT Marketplace: fee={self.platform_fee*100}%")
    
    def _generate_listing_id(self) -> str:
        listing_id = f"LIST_{int(time.time())}_{self.next_id}"
        self.next_id += 1
        return listing_id
    
    def create_listing(self, token_id: str, seller: str, price: float, duration_days: int = 7) -> Optional[str]:
        with self.lock:
            if self.nft.owner_of(token_id) != seller:
                return None
            if price <= 0:
                return None
            listing_id = self._generate_listing_id()
            self.listings[listing_id] = {
                'id': listing_id,
                'token_id': token_id,
                'seller': seller,
                'price': price,
                'created': time.time(),
                'expires': time.time() + duration_days * 86400,
                'status': 'active'
            }
            return listing_id
    
    def buy(self, listing_id: str, buyer: str) -> Dict:
        with self.lock:
            if listing_id not in self.listings:
                return {'success': False, 'error': 'Listing not found'}
            listing = self.listings[listing_id]
            if listing['status'] != 'active':
                return {'success': False, 'error': f'Listing is {listing["status"]}'}
            if time.time() > listing['expires']:
                listing['status'] = 'expired'
                return {'success': False, 'error': 'Listing expired'}
            if self.nft.owner_of(listing['token_id']) != listing['seller']:
                listing['status'] = 'invalid'
                return {'success': False, 'error': 'Seller no longer owns NFT'}
            
            platform_fee = listing['price'] * self.platform_fee
            
            if not self.nft.transfer(listing['seller'], buyer, listing['token_id']):
                return {'success': False, 'error': 'Transfer failed'}
            
            listing['status'] = 'sold'
            listing['buyer'] = buyer
            listing['sold_at'] = time.time()
            
            self.sales.append({
                'listing_id': listing_id,
                'token_id': listing['token_id'],
                'seller': listing['seller'],
                'buyer': buyer,
                'price': listing['price'],
                'platform_fee': platform_fee,
                'timestamp': time.time()
            })
            
            return {'success': True, 'price': listing['price'], 'fee': platform_fee}
    
    def cancel_listing(self, listing_id: str, seller: str) -> bool:
        with self.lock:
            if listing_id not in self.listings:
                return False
            if self.listings[listing_id]['seller'] != seller:
                return False
            if self.listings[listing_id]['status'] != 'active':
                return False
            self.listings[listing_id]['status'] = 'cancelled'
            return True
    
    def get_active_listings(self) -> List[Dict]:
        with self.lock:
            return [l for l in self.listings.values() if l['status'] == 'active' and time.time() < l['expires']]
    
    def get_stats(self) -> Dict:
        with self.lock:
            total_volume = sum(s['price'] for s in self.sales)
            total_fees = sum(s['platform_fee'] for s in self.sales)
            return {
                'total_sales': len(self.sales),
                'total_volume': total_volume,
                'total_fees': total_fees,
                'active_listings': len(self.get_active_listings()),
                'platform_fee_percent': self.platform_fee * 100
            }

# ========== NFT AUCTION ==========

class NFTAuction:
    def __init__(self, nft: NFTStandard):
        self.nft = nft
        self.auctions: Dict[str, Dict] = {}
        self.lock = threading.RLock()
        self.next_id = 1
        print("NFT Auction House инициализирована")
    
    def _generate_auction_id(self) -> str:
        auction_id = f"AUC_{int(time.time())}_{self.next_id}"
        self.next_id += 1
        return auction_id
    
    def create_auction(self, token_id: str, seller: str, starting_price: float, reserve_price: float, duration_hours: int = 24) -> Optional[str]:
        with self.lock:
            if self.nft.owner_of(token_id) != seller:
                return None
            auction_id = self._generate_auction_id()
            self.auctions[auction_id] = {
                'id': auction_id,
                'token_id': token_id,
                'seller': seller,
                'starting_price': starting_price,
                'reserve_price': max(starting_price, reserve_price),
                'current_price': starting_price,
                'current_bidder': None,
                'start_time': time.time(),
                'end_time': time.time() + duration_hours * 3600,
                'status': 'active',
                'bids': []
            }
            return auction_id
    
    def place_bid(self, auction_id: str, bidder: str, amount: float) -> Dict:
        with self.lock:
            if auction_id not in self.auctions:
                return {'success': False, 'error': 'Auction not found'}
            auction = self.auctions[auction_id]
            if auction['status'] != 'active':
                return {'success': False, 'error': f'Auction is {auction["status"]}'}
            if time.time() > auction['end_time']:
                auction['status'] = 'ended'
                return {'success': False, 'error': 'Auction ended'}
            if amount <= auction['current_price']:
                return {'success': False, 'error': f'Minimum bid is {auction["current_price"] + 10}'}
            if bidder == auction['seller']:
                return {'success': False, 'error': 'Cannot bid on own auction'}
            
            auction['bids'].append({'bidder': bidder, 'amount': amount, 'timestamp': time.time()})
            auction['current_price'] = amount
            auction['current_bidder'] = bidder
            return {'success': True, 'current_price': amount}
    
    def get_active_auctions(self) -> List[Dict]:
        with self.lock:
            return [a for a in self.auctions.values() if a['status'] == 'active' and time.time() < a['end_time']]

# ========== NFT BREEDING ==========

class NFTBreeding:
    def __init__(self, nft: NFTStandard):
        self.nft = nft
        self.cooldown: Dict[str, float] = {}
        self.history: List[Dict] = []
        self.lock = threading.RLock()
        self.compatibility = {
            'dragon': ['phoenix', 'lion'],
            'lion': ['wolf', 'dragon'],
            'wolf': ['lion', 'phoenix'],
            'phoenix': ['dragon', 'wolf'],
            'samurai': ['knight', 'ninja'],
            'elf': ['mage', 'knight'],
            'knight': ['samurai', 'elf'],
            'mage': ['elf', 'angel'],
            'angel': ['phoenix', 'mage'],
            'ninja': ['samurai', 'wolf']
        }
        print("NFT Breeding System инициализирована")
    
    def can_breed(self, token_id1: str, token_id2: str) -> Tuple[bool, str]:
        token1 = self.nft.get_token(token_id1)
        token2 = self.nft.get_token(token_id2)
        if not token1 or not token2:
            return False, "NFT not found"
        if token1['owner'] != token2['owner']:
            return False, "NFTs must belong to same owner"
        if token1['type'] == token2['type']:
            return False, "Cannot breed same type"
        if token2['type'] not in self.compatibility.get(token1['type'], []):
            return False, f"{token1['type']} and {token2['type']} are not compatible"
        if token_id1 in self.cooldown and time.time() < self.cooldown[token_id1]:
            return False, "Parent 1 is on cooldown"
        if token_id2 in self.cooldown and time.time() < self.cooldown[token_id2]:
            return False, "Parent 2 is on cooldown"
        return True, "OK"
    
    def breed(self, parent1_id: str, parent2_id: str, owner: str, child_name: str) -> Dict:
        with self.lock:
            can, msg = self.can_breed(parent1_id, parent2_id)
            if not can:
                return {'success': False, 'error': msg}
            
            parent1 = self.nft.get_token(parent1_id)
            parent2 = self.nft.get_token(parent2_id)
            
            stats = {
                'strength': (parent1['stats']['strength'] + parent2['stats']['strength']) // 2,
                'intelligence': (parent1['stats']['intelligence'] + parent2['stats']['intelligence']) // 2,
                'charisma': (parent1['stats']['charisma'] + parent2['stats']['charisma']) // 2,
                'generation': max(parent1.get('generation', 1), parent2.get('generation', 1)) + 1,
                'parents': [parent1_id, parent2_id]
            }
            
            child_id = self.nft.mint(owner, parent1['type'], child_name, stats)
            self.cooldown[parent1_id] = time.time() + 86400
            self.cooldown[parent2_id] = time.time() + 86400
            
            self.history.append({'child_id': child_id, 'parent1': parent1_id, 'parent2': parent2_id, 'timestamp': time.time()})
            
            return {'success': True, 'child_id': child_id, 'child': self.nft.get_token(child_id)}

# ========== ГЛАВНЫЙ МЕНЕДЖЕР NFT ==========

class NFTManager:
    def __init__(self):
        self.nft = NFTStandard()
        self.marketplace = NFTMarketplace(self.nft)
        self.auction = NFTAuction(self.nft)
        self.breeding = NFTBreeding(self.nft)
        print("\nNFT Manager полная версия инициализирована")
    
    def mint(self, owner: str, nft_type: str, name: str = None) -> str:
        return self.nft.mint(owner, nft_type, name)
    
    def transfer(self, from_addr: str, to_addr: str, token_id: str) -> bool:
        return self.nft.transfer(from_addr, to_addr, token_id)
    
    def get_token(self, token_id: str) -> Optional[Dict]:
        return self.nft.get_token(token_id)
    
    def get_owner_tokens(self, owner: str) -> List[Dict]:
        return self.nft.get_tokens_by_owner(owner)
    
    def get_all_tokens(self) -> List[Dict]:
        return self.nft.get_all_tokens()
    
    def get_balance(self, owner: str) -> int:
        return self.nft.balance_of(owner)
    
    def list_for_sale(self, token_id: str, seller: str, price: float, days: int = 7) -> Optional[str]:
        return self.marketplace.create_listing(token_id, seller, price, days)
    
    def buy(self, listing_id: str, buyer: str) -> Dict:
        return self.marketplace.buy(listing_id, buyer)
    
    def cancel_listing(self, listing_id: str, seller: str) -> bool:
        return self.marketplace.cancel_listing(listing_id, seller)
    
    def get_listings(self) -> List[Dict]:
        return self.marketplace.get_active_listings()
    
    def create_auction(self, token_id: str, seller: str, start_price: float, reserve_price: float, hours: int = 24) -> Optional[str]:
        return self.auction.create_auction(token_id, seller, start_price, reserve_price, hours)
    
    def place_bid(self, auction_id: str, bidder: str, amount: float) -> Dict:
        return self.auction.place_bid(auction_id, bidder, amount)
    
    def get_auctions(self) -> List[Dict]:
        return self.auction.get_active_auctions()
    
    def breed(self, parent1_id: str, parent2_id: str, owner: str, child_name: str) -> Dict:
        return self.breeding.breed(parent1_id, parent2_id, owner, child_name)
    
    def get_stats(self) -> Dict:
        return {
            'nft': self.nft.get_stats(),
            'marketplace': self.marketplace.get_stats(),
            'auctions': {'active': len(self.get_auctions())},
            'breeding': {'total_breeds': len(self.breeding.history)}
        }

# ========== ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР ==========

nft_manager = None

def init_nft_system():
    global nft_manager
    nft_manager = NFTManager()
    
    # Создаём тестовые NFT для foundation
    foundation = "foundation"
    nft_types = list(NFT_STATS.keys())
    for i in range(60):
        nft_type = nft_types[i % len(nft_types)]
        name = f"{NFT_STATS[nft_type]['icon']} Герой #{i+1}"
        nft_manager.mint(foundation, nft_type, name)
    
    print(f"\nNFT система инициализирована: {nft_manager.get_stats()['nft']['total_supply']} NFT создано")
    return nft_manager
