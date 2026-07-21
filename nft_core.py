# nft_core.py - Complete NFT system
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import json

from crypto import native

@dataclass
class NFT:
    token_id: str
    name: str
    description: str
    image_url: str
    owner: str
    creator: str
    created_at: datetime
    metadata: Dict
    attributes: Dict
    price: float = 0
    for_sale: bool = False

class NFTMarketplace:
    """Complete NFT marketplace"""
    
    def __init__(self):
        self.tokens: Dict[str, NFT] = {}
        self.balances: Dict[str, List[str]] = {}  # owner -> list of token_ids
        self.listings: Dict[str, float] = {}  # token_id -> price
    
    def mint(self, name: str, description: str, image_url: str, 
             owner: str, creator: str, attributes: Dict = None) -> str:
        """Mint new NFT"""
        token_id = native.sha256_hex(f"{name}{owner}{datetime.now()}".encode())[:16]
        
        nft = NFT(
            token_id=token_id,
            name=name,
            description=description,
            image_url=image_url,
            owner=owner,
            creator=creator,
            created_at=datetime.now(),
            metadata={"standard": "ERC-721", "version": "1.0"},
            attributes=attributes or {},
            price=0,
            for_sale=False
        )
        
        self.tokens[token_id] = nft
        
        if owner not in self.balances:
            self.balances[owner] = []
        self.balances[owner].append(token_id)
        
        print(f"   🎨 NFT Minted: {token_id} | {name}")
        return token_id
    
    def transfer(self, token_id: str, from_addr: str, to_addr: str) -> bool:
        """Transfer NFT ownership"""
        if token_id not in self.tokens:
            return False
        
        nft = self.tokens[token_id]
        if nft.owner != from_addr:
            return False
        
        # Remove from old owner
        if from_addr in self.balances:
            self.balances[from_addr].remove(token_id)
        
        # Add to new owner
        nft.owner = to_addr
        if to_addr not in self.balances:
            self.balances[to_addr] = []
        self.balances[to_addr].append(token_id)
        
        print(f"   🔄 NFT Transferred: {token_id} | {from_addr[:16]}... → {to_addr[:16]}...")
        return True
    
    def list_for_sale(self, token_id: str, price: float) -> bool:
        """List NFT for sale"""
        if token_id in self.tokens:
            self.tokens[token_id].price = price
            self.tokens[token_id].for_sale = True
            self.listings[token_id] = price
            print(f"   💰 NFT Listed: {token_id} | {price} coins")
            return True
        return False
    
    def buy(self, token_id: str, buyer: str, payment: float) -> bool:
        """Buy NFT"""
        if token_id not in self.tokens:
            return False
        
        nft = self.tokens[token_id]
        if not nft.for_sale or nft.price > payment:
            return False
        
        # Transfer ownership
        old_owner = nft.owner
        if self.transfer(token_id, old_owner, buyer):
            nft.for_sale = False
            del self.listings[token_id]
            print(f"   💰 NFT Sold: {token_id} | {nft.price} coins")
            return True
        
        return False
    
    def get_nft(self, token_id: str) -> Optional[NFT]:
        """Get NFT by token_id"""
        return self.tokens.get(token_id)
    
    def get_balance(self, owner: str) -> int:
        """Get NFT balance of owner"""
        return len(self.balances.get(owner, []))
    
    def get_tokens_by_owner(self, owner: str) -> List[str]:
        """Get all tokens owned by address"""
        return self.balances.get(owner, [])
    
    def get_listings(self) -> Dict[str, float]:
        """Get all active listings"""
        return self.listings.copy()
    
    def get_collection(self) -> Dict[str, NFT]:
        """Get entire NFT collection"""
        return self.tokens.copy()

