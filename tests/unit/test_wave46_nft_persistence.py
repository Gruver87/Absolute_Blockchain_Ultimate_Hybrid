"""Wave 46 — NFT marketplace SQLite persistence."""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)


def test_nft_genesis_persists():
    from features.nft import NFTMarketplace
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "n.db"))
    db.initialize()

    m1 = NFTMarketplace(db=db)
    assert m1.get_stats()["total_tokens"] >= 5
    assert m1.get_stats()["persisted"] is True

    m2 = NFTMarketplace(db=db)
    assert m2.get_stats()["total_tokens"] == m1.get_stats()["total_tokens"]


def test_nft_mint_and_buy_persist():
    from features.nft import NFTMarketplace
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "m.db"))
    db.initialize()
    seller = "0x" + "a" * 40
    buyer = "0x" + "b" * 40
    db.update_balance(seller, 1000.0)
    db.update_balance(buyer, 1000.0)

    nft = NFTMarketplace(db=db)
    tid = "test_nft_wave46"
    r = nft.mint(tid, "Wave46", "test", "img", seller, price=50.0)
    assert r["success"] is True
    nft.list_for_sale(tid, seller, 50.0)
    buy = nft.buy(tid, buyer)
    assert buy["success"] is True

    nft2 = NFTMarketplace(db=db)
    tok = nft2.get_token(tid)
    assert tok["owner"] == buyer
    assert nft2.get_stats()["total_sales"] >= 1


def test_db_nft_token_roundtrip():
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "t.db"))
    db.initialize()
    db.save_nft_token({
        "token_id": "x1",
        "name": "Test",
        "description": "d",
        "image_url": "i",
        "owner": "0x1",
        "creator": "0x1",
        "price": 10.0,
        "for_sale": True,
        "created_at": 1700000000,
        "metadata": {"rarity": "rare"},
    })
    rows = db.get_nft_tokens()
    assert len(rows) == 1
    assert rows[0]["metadata"]["rarity"] == "rare"
