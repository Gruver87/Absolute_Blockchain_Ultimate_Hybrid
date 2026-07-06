#!/usr/bin/env python3
import os
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

from runtime.config import Config
from storage.hybrid_database import HybridDatabase


@pytest.fixture
def hybrid_db(tmp_path):
    try:
        import abs_native  # noqa: F401
    except ImportError:
        pytest.skip("abs_native not built")
    cfg = Config()
    cfg.db_path = str(tmp_path / "chainstore")
    cfg.db_engine = "rocksdb"
    db = HybridDatabase(cfg)
    db.initialize()
    yield db
    db.close()


def test_nft_offers_rocks_roundtrip(hybrid_db):
    now = int(time.time())
    hybrid_db.save_nft_offer({
        "offer_id": "offer-1",
        "token_id": "nft-1",
        "bidder": "0x" + "aa" * 20,
        "price": 2.5,
        "expires_at": now + 3600,
        "status": "pending",
        "created_at": now,
    })
    offers = hybrid_db.get_nft_offers()
    assert len(offers) == 1
    assert offers[0]["offer_id"] == "offer-1"
    assert offers[0]["token_id"] == "nft-1"
    assert hybrid_db.get_meta("aux_nft_offers_migrated_v1") is True


def test_nft_auctions_rocks_roundtrip(hybrid_db):
    now = int(time.time())
    hybrid_db.save_nft_auction({
        "auction_id": "auction-1",
        "token_id": "nft-2",
        "seller": "0x" + "bb" * 20,
        "status": "active",
        "ends_at": now + 7200,
        "created_at": now,
        "reserve_price": 10.0,
    })
    auctions = hybrid_db.get_nft_auctions()
    assert len(auctions) == 1
    assert auctions[0]["auction_id"] == "auction-1"
    assert auctions[0]["reserve_price"] == 10.0
    assert hybrid_db.get_meta("aux_nft_auctions_migrated_v1") is True


def test_nft_sales_rocks_roundtrip(hybrid_db):
    now = int(time.time())
    hybrid_db.save_nft_sale({
        "token_id": "nft-3",
        "from": "0x" + "cc" * 20,
        "to": "0x" + "dd" * 20,
        "price": 9.5,
        "type": "buy",
        "timestamp": now,
    })
    sales = hybrid_db.get_nft_sales(limit=10)
    assert len(sales) == 1
    assert sales[0]["token_id"] == "nft-3"
    assert sales[0]["price"] == 9.5
    assert hybrid_db.get_meta("aux_nft_sales_migrated_v1") is True
