#!/usr/bin/env python3
"""NftMarketplacePort fail-closed + adapter smoke (ADR 0016)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from features.nft_ports import NftMarketplaceAdapter, NullNftMarketplacePort


def test_null_nft_port_fail_closed() -> None:
    port = NullNftMarketplacePort()
    assert port.mint("a", "n")["error"] == "nft_disabled"
    assert port.buy("t", "b")["ok"] is False
    assert port.get_token("t") is None
    assert port.list_tokens() == []
    assert port.get_stats()["enabled"] is False


def test_adapter_wraps_simple_marketplace() -> None:
    class _Tok:
        def to_dict(self):
            return {"token_id": "1", "owner": "alice"}

    class _M:
        tokens = {"1": _Tok()}

        def get_stats(self):
            return {"tokens": 1}

        def get_token(self, token_id):
            return self.tokens.get(token_id)

    port = NftMarketplaceAdapter(_M())
    assert port.get_token("1")["owner"] == "alice"
    assert port.get_stats()["adr"] == "0016"
    assert port.list_tokens("alice")[0]["token_id"] == "1"
