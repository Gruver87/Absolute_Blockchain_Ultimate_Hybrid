#!/usr/bin/env python3
"""NFT mint/buy use db.atomic() UoW when available (ADR 0016 Profile C)."""
from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)


def test_nft_mint_buy_report_uow_atomic():
    from features.nft import NFTMarketplace
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "nft_uow.db"))
    db.initialize()
    seller = "0x" + "a" * 40
    buyer = "0x" + "b" * 40
    db.update_balance(seller, 1000.0)
    db.update_balance(buyer, 1000.0)

    nft = NFTMarketplace(db=db)
    assert nft.get_stats()["uow_atomic"] is True
    assert nft.get_stats()["tier"] == "app-profile"

    before = db.get_balance(seller)
    r = nft.mint("uow_tok", "UoW", "t", "img", seller, price=10.0)
    assert r["success"] is True
    assert r.get("uow_atomic") is True
    assert db.get_balance(seller) == before - nft.MINT_FEE

    buy = nft.buy("uow_tok", buyer)
    assert buy["success"] is True
    assert buy.get("uow_atomic") is True
    assert nft.get_token("uow_tok")["owner"] == buyer


def test_nft_mint_rolls_back_memory_on_uow_failure():
    from features.nft import NFTMarketplace

    class _BrokenAtomic:
        def atomic(self):
            raise RuntimeError("forced_uow_fail")

        def get_balance(self, _a):
            return 100.0

        def update_balance(self, _a, _d):
            return 0.0

        def get_nft_tokens(self):
            return []

    nft = NFTMarketplace(db=_BrokenAtomic())
    # Clear genesis noise for assertion
    nft.tokens.clear()
    r = nft.mint("x", "n", "d", "i", "0xcreator", 0.0)
    assert r["success"] is False
    assert "nft_uow_failed" in r["error"]
    assert "x" not in nft.tokens
