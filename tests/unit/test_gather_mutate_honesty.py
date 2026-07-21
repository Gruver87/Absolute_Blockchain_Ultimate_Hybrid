#!/usr/bin/env python3
"""v1.3.26 honesty: remaining gather, Rocks mutate, attestation errors, BlockBuilder."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_remaining_broadcast_kinds_recorded():
    p2p = Path("network/p2p_node.py").read_text(encoding="utf-8")
    for kind in (
        'kind="cross_shard_ack"',
        'kind="cross_shard_tx"',
        'kind="shard_migration"',
        'kind="validator_register"',
    ):
        assert kind in p2p


def test_rocks_mutate_paths_use_loads_helper():
    rocks = Path("storage/rocks_store.py").read_text(encoding="utf-8")
    assert 'context=f"slash_validator' in rocks
    assert 'context=f"bridge_lock' in rocks
    assert 'context="burn_total"' in rocks


def test_consensus_attestation_missing_error():
    http_py = Path("api/http.py").read_text(encoding="utf-8")
    assert "consensus_adapter_missing" in http_py
    assert "slashing_engine_missing" in http_py
    assert "sharding_missing" in http_py


def test_blockbuilder_not_advertised_as_enabled():
    main_py = Path("main.py").read_text(encoding="utf-8")
    assert "forge still uses blockchain.create_block — not wired" in main_py
    assert "BlockBuilder: enabled (deterministic tx selection)" not in main_py


def test_broadcast_fail_alert_present():
    alerts = Path("deploy/prometheus/alerts.yml").read_text(encoding="utf-8")
    assert "AbsoluteP2PBroadcastFailBurst" in alerts
    assert 'kind="broadcast_fail"' in alerts
