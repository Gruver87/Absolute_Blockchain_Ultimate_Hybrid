#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ABSOLUTE BLOCKCHAIN - NFT MARKETPLACE ENHANCED (РАБОЧАЯ ВЕРСИЯ)
"""

import time
import secrets
import threading
from typing import Dict, List, Optional

class NFTMarketplaceEnhanced:
    def __init__(self, nft_manager=None):
        self.nft = nft_manager
        self.listings = {}
        self.offers = {}
        self.auctions = {}
        self.sales = []
        self.platform_fee = 0.02
        self.next_id = 1
        self.lock = threading.RLock()
        print("🏪 NFT Marketplace Enhanced initialized")
    
    def _generate_id(self, prefix="LIST"):
        result = f"{prefix}_{int(time.time())}_{self.next_id}_{secrets.token_hex(4)}"
        self.next_id += 1
        return result
    
    def create_listing(self, token_id, seller, price, days=7):
        if price <= 0:
            return None
        listing_id = self._generate_id("LIST")
        self.listings[listing_id] = {
            "id": listing_id,
            "token_id": token_id,
            "seller": seller,
            "price": price,
            "currency": "ABS",
            "created_at": time.time(),
            "expires_at": time.time() + days * 86400,
            "status": "active"
        }
        print(f"📋 Listing created: {token_id[:16]}... for {price} ABS")
        return listing_id
    
    def buy(self, listing_id, buyer):
        if listing_id not in self.listings:
            return {"success": False, "error": "Listing not found"}
        
        listing = self.listings[listing_id]
        if listing["status"] != "active":
            return {"success": False, "error": f"Listing is {listing['status']}"}
        
        if listing.get("expires_at") and time.time() > listing["expires_at"]:
            listing["status"] = "expired"
            return {"success": False, "error": "Listing expired"}
        
        if buyer == listing["seller"]:
            return {"success": False, "error": "Cannot buy your own NFT"}
        
        platform_fee = listing["price"] * self.platform_fee
        
        listing["status"] = "sold"
        listing["buyer"] = buyer
        listing["sold_at"] = time.time()
        
        sale = {
            "id": secrets.token_hex(8),
            "listing_id": listing_id,
            "token_id": listing["token_id"],
            "seller": listing["seller"],
            "buyer": buyer,
            "price": listing["price"],
            "platform_fee": platform_fee,
            "timestamp": time.time()
        }
        self.sales.append(sale)
        
        print(f"💰 NFT sold: {listing['token_id'][:16]}... for {listing['price']} ABS")
        
        return {"success": True, "sale": sale, "price": listing["price"]}
    
    def create_offer(self, token_id, bidder, price, hours=24):
        if price <= 0:
            return None
        
        offer_id = self._generate_id("OFFER")
        self.offers[offer_id] = {
            "id": offer_id,
            "token_id": token_id,
            "bidder": bidder,
            "price": price,
            "currency": "ABS",
            "created_at": time.time(),
            "expires_at": time.time() + hours * 3600,
            "status": "active"
        }
        print(f"💭 Offer created: {price} ABS for {token_id[:16]}...")
        return offer_id
    
    def accept_offer(self, offer_id, seller):
        if offer_id not in self.offers:
            return {"success": False, "error": "Offer not found"}
        
        offer = self.offers[offer_id]
        if offer["status"] != "active":
            return {"success": False, "error": f"Offer is {offer['status']}"}
        
        listing_id = self.create_listing(offer["token_id"], seller, offer["price"], 1)
        if not listing_id:
            return {"success": False, "error": "Failed to create listing"}
        
        result = self.buy(listing_id, offer["bidder"])
        
        if result["success"]:
            offer["status"] = "accepted"
            print(f"✅ Offer accepted! NFT sold for {offer['price']}")
        
        return result
    
    def create_auction(self, token_id, seller, start_price, reserve_price, hours=24, auction_type="english"):
        if start_price <= 0:
            return None
        
        auction_id = self._generate_id("AUCTION")
        self.auctions[auction_id] = {
            "id": auction_id,
            "token_id": token_id,
            "seller": seller,
            "starting_price": start_price,
            "reserve_price": reserve_price if reserve_price > start_price else start_price,
            "current_price": start_price,
            "current_bidder": None,
            "start_time": time.time(),
            "end_time": time.time() + hours * 3600,
            "auction_type": auction_type,
            "bids": [],
            "status": "active"
        }
        print(f"🔨 Auction created: {token_id[:16]}... start {start_price}, reserve {reserve_price}")
        return auction_id
    
    def place_bid(self, auction_id, bidder, amount):
        if auction_id not in self.auctions:
            return {"success": False, "error": "Auction not found"}
        
        auction = self.auctions[auction_id]
        if auction["status"] != "active":
            return {"success": False, "error": f"Auction is {auction['status']}"}
        
        if time.time() > auction["end_time"]:
            auction["status"] = "ended"
            return {"success": False, "error": "Auction ended"}
        
        if bidder == auction["seller"]:
            return {"success": False, "error": "Cannot bid on own auction"}
        
        min_bid = auction["current_price"] + 10
        if amount < min_bid:
            return {"success": False, "error": f"Minimum bid is {min_bid}"}
        
        bid = {"bidder": bidder, "amount": amount, "timestamp": time.time()}
        auction["bids"].append(bid)
        auction["current_price"] = amount
        auction["current_bidder"] = bidder
        
        print(f"💰 New bid: {amount} from {bidder[:16]}...")
        
        return {"success": True, "current_price": amount}
    
    def get_listings(self):
        return [l for l in self.listings.values() if l["status"] == "active"]
    
    def get_auctions(self):
        return [a for a in self.auctions.values() if a["status"] == "active"]
    
    def get_sales_history(self, token_id=None, limit=50):
        if token_id:
            return [s for s in self.sales if s.get("token_id") == token_id][-limit:]
        return self.sales[-limit:]
    
    def get_stats(self):
        total_volume = sum(s.get("price", 0) for s in self.sales)
        return {
            "total_sales": len(self.sales),
            "total_volume": total_volume,
            "active_listings": len(self.get_listings()),
            "active_auctions": len(self.get_auctions()),
            "platform_fee_percent": self.platform_fee * 100
        }

marketplace_enhanced = NFTMarketplaceEnhanced()

def init_marketplace(nft_manager):
    global marketplace_enhanced
    marketplace_enhanced = NFTMarketplaceEnhanced(nft_manager)
    return marketplace_enhanced
