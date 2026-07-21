#!/usr/bin/env python3
"""v1.3.35 honesty: MiniVM/ZK/Lightning/DAO/relayer status labels."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_minivm_feature_gate_and_labels():
    main = Path("main.py").read_text(encoding="utf-8")
    assert "feature_minivm" in main
    assert "MiniVM: disabled" in main
    cfg = Path("runtime/config.py").read_text(encoding="utf-8")
    assert "FEATURE_MINIVM" in cfg
    assert 'self.feature_minivm = env_bool("FEATURE_MINIVM", False)' in cfg
    http = Path("api/http.py").read_text(encoding="utf-8")
    assert '"/minivm/deploy"' in http
    assert "r_and_d" in http


def test_lightning_direct_only():
    ln = Path("features/lightning.py").read_text(encoding="utf-8")
    assert '"routing_enabled": False' in ln
    assert "direct_channel_only" in ln
    assert "Multi-hop remote messaging is not implemented" in ln
    http = Path("api/http.py").read_text(encoding="utf-8")
    assert "multi-hop lightning routing not implemented" in http


def test_dao_vote_prod_blocked():
    http = Path("api/http.py").read_text(encoding="utf-8")
    assert "unsigned DAO vote forbidden in prod" in http
    assert '"/pools/dao/vote"' in http
    assert "signature_bound" in http


def test_zk_no_invented_validity_no_get_privkey():
    http = Path("api/http.py").read_text(encoding="utf-8")
    assert "zk_missing" in http
    assert "private keys in query forbidden" in http
    assert "value >= min_v and value <= max_v" not in http


def test_relayer_live_not_binary_smoke():
    http = Path("api/http.py").read_text(encoding="utf-8")
    assert '"bridge_rust_binary_healthy"' in http
    assert '"bridge_relayer_live": False' in http
    assert '"relayer_observed": False' in http
