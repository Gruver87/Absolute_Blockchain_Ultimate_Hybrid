#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NFT Marketplace — встроен в Absolute Blockchain.
Перенесён из nft_core.py и расширен поддержкой БД и EventBus.
"""

import json
import time
import threading
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class NFTToken:
    token_id: str
    name: str
    description: str
    image_url: str
    owner: str
    creator: str
    price: float = 0.0
    for_sale: bool = False
    created_at: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "token_id": self.token_id,
            "name": self.name,
            "description": self.description,
            "image_url": self.image_url,
            "owner": self.owner,
            "creator": self.creator,
            "price": self.price,
            "for_sale": self.for_sale,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


class NFTMarketplace:
    """
    NFT маркетплейс, интегрированный с балансами блокчейна.
    При покупке/продаже ABS-балансы обновляются через db.
    """

    MINT_FEE = 1.0   # стоимость создания NFT в ABS
    ROYALTY = 0.05   # 5% роялти создателю при каждой продаже

    def __init__(self, db=None, bus=None):
        self.db = db      # Database (может быть None в standalone-режиме)
        self.bus = bus    # EventBus
        self.tokens: Dict[str, NFTToken] = {}
        self.lock = threading.RLock()
        self._load_genesis_collection()

    def _load_genesis_collection(self):
        """Начальная коллекция Genesis."""
        genesis = [
            ("abs_genesis_crown",    "Absolute Crown",    "The ultimate crown of the Absolute Kingdom", "crown",    100.0),
            ("abs_quantum_guardian", "Quantum Guardian",  "Guardian of the quantum realm",              "guardian", 200.0),
            ("abs_genesis_block",    "Genesis Block",     "The very first block of Absolute chain",     "block",    500.0),
            ("abs_elemental_master", "Elemental Master",  "Master of all four elements",                "master",   300.0),
            ("abs_wisdom_relic",     "Wisdom Relic",      "Ancient artifact of wisdom",                 "relic",    150.0),
        ]
        for tid, name, desc, img, price in genesis:
            self._mint_internal(tid, name, desc, img, "0xgenesis", price)

    def _mint_internal(self, token_id, name, description, image_url, creator, price):
        if token_id not in self.tokens:
            self.tokens[token_id] = NFTToken(
                token_id=token_id, name=name, description=description,
                image_url=image_url, owner=creator, creator=creator,
                price=price, for_sale=(price > 0),
            )

    # ── Создание NFT ─────────────────────────────────────────────────────────

    def mint(self, token_id: str, name: str, description: str,
             image_url: str, creator: str, price: float = 0.0) -> Dict:
        """Создать новый NFT. Списывает MINT_FEE с создателя."""
        with self.lock:
            if token_id in self.tokens:
                return {"success": False, "error": "token_id already exists"}

            if self.db:
                balance = self.db.get_balance(creator)
                if balance < self.MINT_FEE:
                    return {"success": False, "error": f"Need {self.MINT_FEE} ABS to mint"}
                self.db.update_balance(creator, -self.MINT_FEE)

            self.tokens[token_id] = NFTToken(
                token_id=token_id, name=name, description=description,
                image_url=image_url, owner=creator, creator=creator,
                price=price, for_sale=(price > 0),
            )

            if self.bus:
                self.bus.emit("nft.minted", {"token_id": token_id, "creator": creator})

            return {"success": True, "token_id": token_id}

    # ── Торговля ─────────────────────────────────────────────────────────────

    def list_for_sale(self, token_id: str, owner: str, price: float) -> Dict:
        with self.lock:
            if token_id not in self.tokens:
                return {"success": False, "error": "not found"}
            t = self.tokens[token_id]
            if t.owner != owner:
                return {"success": False, "error": "not owner"}
            t.price = price
            t.for_sale = True
            return {"success": True, "token_id": token_id, "price": price}

    def buy(self, token_id: str, buyer: str) -> Dict:
        """Покупка NFT. ABS переводится продавцу и создателю (роялти)."""
        with self.lock:
            if token_id not in self.tokens:
                return {"success": False, "error": "not found"}
            t = self.tokens[token_id]
            if not t.for_sale:
                return {"success": False, "error": "not for sale"}
            if buyer == t.owner:
                return {"success": False, "error": "already owner"}

            price = t.price

            if self.db:
                if self.db.get_balance(buyer) < price:
                    return {"success": False, "error": "insufficient balance"}
                royalty = price * self.ROYALTY
                seller_amount = price - royalty
                self.db.update_balance(buyer, -price)
                self.db.update_balance(t.owner, seller_amount)
                if t.creator != t.owner:
                    self.db.update_balance(t.creator, royalty)

            old_owner = t.owner
            t.owner = buyer
            t.for_sale = False

            if self.bus:
                self.bus.emit("nft.sold", {
                    "token_id": token_id, "buyer": buyer,
                    "seller": old_owner, "price": price,
                })

            return {"success": True, "token_id": token_id,
                    "buyer": buyer, "price": price}

    def transfer(self, token_id: str, from_addr: str, to_addr: str) -> Dict:
        with self.lock:
            if token_id not in self.tokens:
                return {"success": False, "error": "not found"}
            t = self.tokens[token_id]
            if t.owner != from_addr:
                return {"success": False, "error": "not owner"}
            t.owner = to_addr
            t.for_sale = False
            return {"success": True}

    # ── Геттеры ──────────────────────────────────────────────────────────────

    def get_token(self, token_id: str) -> Optional[Dict]:
        with self.lock:
            t = self.tokens.get(token_id)
            return t.to_dict() if t else None

    def get_by_owner(self, owner: str) -> List[Dict]:
        with self.lock:
            return [t.to_dict() for t in self.tokens.values() if t.owner == owner]

    def get_on_sale(self) -> List[Dict]:
        with self.lock:
            return [t.to_dict() for t in self.tokens.values() if t.for_sale]

    def get_all(self) -> List[Dict]:
        with self.lock:
            return [t.to_dict() for t in self.tokens.values()]

    def get_stats(self) -> Dict:
        with self.lock:
            return {
                "total_tokens": len(self.tokens),
                "on_sale": sum(1 for t in self.tokens.values() if t.for_sale),
                "unique_owners": len({t.owner for t in self.tokens.values()}),
                "total_value": sum(t.price for t in self.tokens.values() if t.for_sale),
                "mint_fee": self.MINT_FEE,
                "royalty_pct": self.ROYALTY * 100,
            }
