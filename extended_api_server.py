#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ABSOLUTE BLOCKCHAIN - ДОПОЛНИТЕЛЬНЫЙ API СЕРВЕР
Порт: 8081
Модули: Real World Oracles, Dynamic Sharding, NFT Marketplace Enhanced
"""

import json
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Импортируем модули
try:
    from real_world_oracles import oracle_manager
    print("✅ Real World Oracles loaded")
except Exception as e:
    print(f"❌ Oracles error: {e}")
    oracle_manager = None

try:
    from dynamic_sharding import sharding_manager
    print("✅ Dynamic Sharding loaded")
except Exception as e:
    print(f"❌ Sharding error: {e}")
    sharding_manager = None

try:
    from nft_marketplace_enhanced import marketplace_enhanced
    print("✅ NFT Marketplace Enhanced loaded")
except Exception as e:
    print(f"❌ Marketplace error: {e}")
    marketplace_enhanced = None

# Создаём приложение
app = FastAPI(title="Absolute Blockchain Extended API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== REAL WORLD ORACLES ENDPOINTS ==========

@app.get("/api/oracle/price")
async def oracle_price(symbol: str = Query("bitcoin", description="Cryptocurrency symbol")):
    if oracle_manager:
        return oracle_manager.get_price(symbol)
    return {"error": "Oracles not available"}

@app.get("/api/oracle/weather")
async def oracle_weather(city: str = Query("London", description="City name")):
    if oracle_manager:
        return oracle_manager.get_weather(city)
    return {"error": "Oracles not available"}

@app.get("/api/oracle/news")
async def oracle_news(currency: str = None, limit: int = 10):
    if oracle_manager:
        return oracle_manager.get_news(currency, limit)
    return {"error": "Oracles not available"}

@app.get("/api/oracle/all")
async def oracle_all():
    if oracle_manager:
        return oracle_manager.get_all_data()
    return {"error": "Oracles not available"}

@app.get("/api/oracle/stats")
async def oracle_stats():
    if oracle_manager:
        return oracle_manager.get_stats()
    return {"error": "Oracles not available"}

# ========== DYNAMIC SHARDING ENDPOINTS ==========

@app.get("/api/sharding/stats")
async def sharding_stats():
    if sharding_manager:
        return sharding_manager.get_stats()
    return {"error": "Sharding not available"}

@app.get("/api/sharding/shards")
async def sharding_shards():
    if sharding_manager:
        return [s.get_stats() for s in sharding_manager.shards.values()]
    return {"error": "Sharding not available"}

@app.get("/api/sharding/shard")
async def sharding_shard(shard_id: int = 0):
    if sharding_manager and shard_id in sharding_manager.shards:
        return sharding_manager.shards[shard_id].get_stats()
    return {"error": "Shard not found"}

# ========== NFT MARKETPLACE ENHANCED ENDPOINTS ==========

@app.get("/api/nft/marketplace_stats")
async def marketplace_stats():
    if marketplace_enhanced:
        return marketplace_enhanced.get_stats()
    return {"error": "Marketplace not available"}

@app.get("/api/nft/listings")
async def marketplace_listings():
    if marketplace_enhanced:
        return marketplace_enhanced.get_listings()
    return {"error": "Marketplace not available"}

@app.get("/api/nft/auctions")
async def marketplace_auctions():
    if marketplace_enhanced:
        return marketplace_enhanced.get_auctions()
    return {"error": "Marketplace not available"}

@app.get("/api/nft/sales")
async def marketplace_sales(token_id: str = None, limit: int = 50):
    if marketplace_enhanced:
        return marketplace_enhanced.get_sales_history(token_id, limit)
    return {"error": "Marketplace not available"}

@app.get("/api/nft/offers")
async def marketplace_offers():
    if marketplace_enhanced:
        return list(marketplace_enhanced.offers.values())
    return {"error": "Marketplace not available"}

# ========== POST ENDPOINTS ==========

from pydantic import BaseModel

class OfferRequest(BaseModel):
    token_id: str
    bidder: str
    price: float
    hours: int = 24

class AcceptOfferRequest(BaseModel):
    offer_id: str
    seller: str

class AuctionRequest(BaseModel):
    token_id: str
    seller: str
    start_price: float
    reserve_price: float
    hours: int = 24
    auction_type: str = "english"

class BidRequest(BaseModel):
    auction_id: str
    bidder: str
    amount: float

class ListingRequest(BaseModel):
    token_id: str
    seller: str
    price: float
    days: int = 7

class BuyRequest(BaseModel):
    listing_id: str
    buyer: str

@app.post("/api/nft/offer")
async def create_offer(request: OfferRequest):
    if marketplace_enhanced:
        result = marketplace_enhanced.create_offer(request.token_id, request.bidder, request.price, request.hours)
        if result:
            return {"success": True, "offer_id": result}
        return {"success": False, "error": "Failed to create offer"}
    return {"error": "Marketplace not available"}

@app.post("/api/nft/accept_offer")
async def accept_offer(request: AcceptOfferRequest):
    if marketplace_enhanced:
        return marketplace_enhanced.accept_offer(request.offer_id, request.seller)
    return {"error": "Marketplace not available"}

@app.post("/api/nft/auction")
async def create_auction(request: AuctionRequest):
    if marketplace_enhanced:
        result = marketplace_enhanced.create_auction(
            request.token_id, request.seller, request.start_price, 
            request.reserve_price, request.hours, request.auction_type
        )
        if result:
            return {"success": True, "auction_id": result}
        return {"success": False, "error": "Failed to create auction"}
    return {"error": "Marketplace not available"}

@app.post("/api/nft/bid")
async def place_bid(request: BidRequest):
    if marketplace_enhanced:
        return marketplace_enhanced.place_bid(request.auction_id, request.bidder, request.amount)
    return {"error": "Marketplace not available"}

@app.post("/api/nft/list")
async def create_listing(request: ListingRequest):
    if marketplace_enhanced:
        result = marketplace_enhanced.create_listing(request.token_id, request.seller, request.price, request.days)
        if result:
            return {"success": True, "listing_id": result}
        return {"success": False, "error": "Failed to create listing"}
    return {"error": "Marketplace not available"}

@app.post("/api/nft/buy")
async def buy_nft(request: BuyRequest):
    if marketplace_enhanced:
        return marketplace_enhanced.buy(request.listing_id, request.buyer)
    return {"error": "Marketplace not available"}

# ========== HEALTH CHECK ==========

@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "modules": {
            "oracles": oracle_manager is not None,
            "sharding": sharding_manager is not None,
            "marketplace": marketplace_enhanced is not None
        }
    }

@app.get("/")
async def root():
    return {
        "name": "Absolute Blockchain Extended API",
        "version": "1.0",
        "endpoints": [
            "/api/oracle/price",
            "/api/oracle/weather", 
            "/api/oracle/news",
            "/api/sharding/stats",
            "/api/nft/marketplace_stats",
            "/api/nft/listings",
            "/api/nft/auctions"
        ]
    }

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🌐 ABSOLUTE BLOCKCHAIN EXTENDED API SERVER")
    print("=" * 60)
    print(f"📡 Server: http://localhost:8081")
    print(f"📚 Docs: http://localhost:8081/docs")
    print("=" * 60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8081)
