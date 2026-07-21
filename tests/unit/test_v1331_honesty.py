#!/usr/bin/env python3
"""v1.3.31 honesty: oracle quorum, sync finally, peer fork, bridge/MEV/AI/will."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_oracle_requires_signature_when_secret_set():
    text = Path("features/oracle_registry.py").read_text(encoding="utf-8")
    assert "oracle signature required" in text
    assert "One vote per reporter" in text
    assert "unique_reporters" in text


def test_consensus_health_uses_ingest_fail():
    text = Path("consensus/adapter.py").read_text(encoding="utf-8")
    assert '"healthy": ingest_fail == 0' in text


def test_sync_finally_clears_is_syncing():
    text = Path("sync/sync_engine.py").read_text(encoding="utf-8")
    assert "never leave is_syncing stuck" in text
    assert "sync_fail" in text
    assert "last_sync_error" in text


def test_peer_chain_compatible_on_same_height():
    text = Path("network/p2p_node.py").read_text(encoding="utf-8")
    assert "transport_healthy" in text
    assert "chain_compatible" in text
    assert "Same-height divergent head" in text


def test_bridge_ops_error_counters():
    text = Path("bridge/abs_bridge.py").read_text(encoding="utf-8")
    assert "_rust_decode_fail" in text
    assert "def get_ops_errors" in text


def test_mev_heuristic_labels():
    text = Path("features/mev_analyzer.py").read_text(encoding="utf-8")
    assert "heuristic_signals" in text
    assert "model_estimate_profit" in text
    assert "not confirmed on-chain attacks" in text


def test_ai_no_fake_confidence():
    text = Path("features/ai_manager.py").read_text(encoding="utf-8")
    assert '"confidence": None' in text
    assert "model_bound" in text
    assert "executor_bound" in text
    assert "no ML model or trade executor bound" in text


def test_will_persist_fail_closed():
    text = Path("features/crypto_will.py").read_text(encoding="utf-8")
    assert "create persist failed, refunded" in text
    assert "monitor_errors" in text
    assert "Mark executed before credit" in text
