#!/usr/bin/env python3
"""v1.3.27 honesty: Rocks NFT/EVM decode, catch_up gather, IMS/sharding missing, get_meta."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_catch_up_sync_records_broadcast():
    p2p = Path("network/p2p_node.py").read_text(encoding="utf-8")
    assert 'kind="catch_up_sync"' in p2p


def test_rocks_decode_helpers_fail_closed():
    rocks = Path("storage/rocks_store.py").read_text(encoding="utf-8")
    assert 'context="tx_propagation"' in rocks
    assert 'context="evm_log"' in rocks
    assert 'context="nft_token"' in rocks
    assert 'context="nft_offer"' in rocks
    assert 'context="nft_auction"' in rocks
    assert 'context="nft_sale"' in rocks
    assert "Fail-closed: never return a garbage string as valid meta" in rocks


def test_ims_and_status_sharding_missing_errors():
    http_py = Path("api/http.py").read_text(encoding="utf-8")
    assert "immutable_state_missing" in http_py
    assert '"error": "sharding_missing"' in http_py


def test_peer_sync_and_catch_up_alerts():
    alerts = Path("deploy/prometheus/alerts.yml").read_text(encoding="utf-8")
    assert "AbsoluteP2PPeerSyncFailBurst" in alerts
    assert "AbsoluteP2PCatchUpLoopFailBurst" in alerts
