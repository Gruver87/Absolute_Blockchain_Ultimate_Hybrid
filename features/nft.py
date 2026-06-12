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
        self.offers: Dict[str, Dict] = {}
        self.auctions: Dict[str, Dict] = {}
        self.sales_history: List[Dict] = []
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
                "total_sales": len(self.sales_history),
                "total_offers": len(self.offers),
                "active_auctions": sum(1 for a in self.auctions.values() if a.get("status") == "active"),
            }

    # ── Offers ────────────────────────────────────────────────────────────────

    def make_offer(self, token_id: str, bidder: str, price: float,
                   hours: int = 24) -> Optional[str]:
        """Create a purchase offer for any NFT (not just for-sale ones)."""
        import hashlib
        with self.lock:
            if token_id not in self.tokens:
                return None
            offer_id = hashlib.sha256(
                f"{token_id}{bidder}{price}{time.time()}".encode()
            ).hexdigest()[:16]
            self.offers[offer_id] = {
                "offer_id": offer_id,
                "token_id": token_id,
                "bidder": bidder,
                "price": price,
                "expires_at": int(time.time()) + hours * 3600,
                "status": "pending",
                "created_at": int(time.time()),
            }
            return offer_id

    def accept_offer(self, offer_id: str, seller: str) -> Dict:
        """Accept an offer — transfer NFT to bidder."""
        with self.lock:
            offer = self.offers.get(offer_id)
            if not offer or offer["status"] != "pending":
                return {"success": False, "error": "Offer not found or expired"}
            token_id = offer["token_id"]
            t = self.tokens.get(token_id)
            if not t or t.owner != seller:
                return {"success": False, "error": "Not token owner"}
            # Transfer
            price = offer["price"]
            if self.db:
                if self.db.get_balance(offer["bidder"]) < price:
                    return {"success": False, "error": "Bidder has insufficient balance"}
                royalty = price * self.ROYALTY
                self.db.update_balance(offer["bidder"], -price)
                self.db.update_balance(seller, price - royalty)
                if t.creator != seller:
                    self.db.update_balance(t.creator, royalty)
            old_owner = t.owner
            t.owner = offer["bidder"]
            t.for_sale = False
            offer["status"] = "accepted"
            self.sales_history.append({
                "token_id": token_id, "from": old_owner,
                "to": offer["bidder"], "price": price,
                "type": "offer", "timestamp": int(time.time()),
            })
            if self.bus:
                self.bus.emit("nft.offer_accepted", {"offer_id": offer_id, "token_id": token_id})
            return {"success": True, "offer_id": offer_id, "token_id": token_id, "price": price}

    def get_offers(self, token_id: str = None) -> List[Dict]:
        with self.lock:
            now = int(time.time())
            offers = [o for o in self.offers.values()
                      if (token_id is None or o["token_id"] == token_id)
                      and o["expires_at"] > now]
            return offers

    # ── Auctions ──────────────────────────────────────────────────────────────

    def create_auction(self, token_id: str, seller: str, start_price: float,
                       reserve_price: float = 0.0, hours: int = 24,
                       auction_type: str = "english") -> Optional[str]:
        """Create an English auction for an NFT."""
        import hashlib
        with self.lock:
            t = self.tokens.get(token_id)
            if not t or t.owner != seller:
                return None
            auction_id = hashlib.sha256(
                f"{token_id}{seller}{time.time()}".encode()
            ).hexdigest()[:16]
            self.auctions[auction_id] = {
                "auction_id": auction_id,
                "token_id": token_id,
                "seller": seller,
                "start_price": start_price,
                "reserve_price": reserve_price,
                "current_bid": start_price,
                "current_bidder": None,
                "auction_type": auction_type,
                "ends_at": int(time.time()) + hours * 3600,
                "status": "active",
                "bids": [],
                "created_at": int(time.time()),
            }
            return auction_id

    def place_bid(self, auction_id: str, bidder: str, amount: float) -> Dict:
        with self.lock:
            auction = self.auctions.get(auction_id)
            if not auction or auction["status"] != "active":
                return {"success": False, "error": "Auction not found or ended"}
            if int(time.time()) > auction["ends_at"]:
                auction["status"] = "ended"
                return {"success": False, "error": "Auction has ended"}
            if amount <= auction["current_bid"]:
                return {"success": False, "error": f"Bid must be > {auction['current_bid']}"}
            auction["bids"].append({"bidder": bidder, "amount": amount, "ts": int(time.time())})
            auction["current_bid"] = amount
            auction["current_bidder"] = bidder
            return {"success": True, "auction_id": auction_id,
                    "current_bid": amount, "bidder": bidder}

    def finalize_auction(self, auction_id: str) -> Dict:
        with self.lock:
            auction = self.auctions.get(auction_id)
            if not auction:
                return {"success": False, "error": "Auction not found"}
            if auction["status"] != "active":
                return {"success": False, "error": "Auction already finalized"}
            auction["status"] = "finalized"
            winner = auction["current_bidder"]
            price = auction["current_bid"]
            if winner and price >= auction.get("reserve_price", 0):
                token_id = auction["token_id"]
                t = self.tokens.get(token_id)
                if t:
                    old_owner = t.owner
                    if self.db:
                        royalty = price * self.ROYALTY
                        self.db.update_balance(winner, -price)
                        self.db.update_balance(old_owner, price - royalty)
                        if t.creator != old_owner:
                            self.db.update_balance(t.creator, royalty)
                    t.owner = winner
                    t.for_sale = False
                    self.sales_history.append({
                        "token_id": token_id, "from": old_owner, "to": winner,
                        "price": price, "type": "auction", "timestamp": int(time.time()),
                    })
                return {"success": True, "auction_id": auction_id,
                        "winner": winner, "price": price}
            return {"success": True, "auction_id": auction_id,
                    "message": "Reserve price not met — no sale"}

    def get_auctions(self, active_only: bool = False) -> List[Dict]:
        with self.lock:
            auctions = list(self.auctions.values())
            if active_only:
                auctions = [a for a in auctions if a["status"] == "active"]
            return auctions

    def get_sales_history(self, token_id: str = None, limit: int = 50) -> List[Dict]:
        with self.lock:
            sales = self.sales_history
            if token_id:
                sales = [s for s in sales if s["token_id"] == token_id]
            return sales[-limit:][::-1]
