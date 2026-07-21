#!/usr/bin/env python3
"""v1.3.33 honesty: bridge event replay/atomic credit, plasma force, smart accounts."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_bridge_event_replay_key():
    text = Path("bridge/abs_bridge.py").read_text(encoding="utf-8")
    assert "claim_and_credit_bridge_event" in text
    assert "l1_event_bound" in text
    assert "from_chain:event_tx_hash:log_index" in text
    db = Path("storage/database.py").read_text(encoding="utf-8")
    assert "def claim_and_credit_bridge_event" in db
    assert "source event identity" in db
    rocks = Path("storage/rocks_store.py").read_text(encoding="utf-8")
    assert "def claim_and_credit_bridge_event" in rocks


def test_plasma_force_forbidden_in_prod():
    text = Path("api/http.py").read_text(encoding="utf-8")
    assert "force plasma finalize forbidden in prod" in text


def test_smart_accounts_feature_gate():
    main = Path("main.py").read_text(encoding="utf-8")
    assert "feature_smart_accounts" in main
    assert "execution_bound=false" in main
    cfg = Path("runtime/config.py").read_text(encoding="utf-8")
    assert 'FEATURE_SMART_ACCOUNTS' in cfg
    assert 'self.feature_smart_accounts = env_bool("FEATURE_SMART_ACCOUNTS", False)' in cfg
    sa = Path("features/smart_accounts.py").read_text(encoding="utf-8")
    assert "execution_bound" in sa
    assert "in_memory_registry" in sa


def test_relayer_status_event_bound_honesty():
    text = Path("api/http.py").read_text(encoding="utf-8")
    assert "event_binding_mode" in text
    assert "l1_event_abi_decoded" in text
