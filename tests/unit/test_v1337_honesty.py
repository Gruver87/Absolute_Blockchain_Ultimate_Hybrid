#!/usr/bin/env python3
"""v1.3.37 honesty: bridge L1 proof / blind confirm / light / PBS / AI."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_prod_bridge_l1_proof_not_weakenable_via_env():
    cfg = Path("runtime/config.py").read_text(encoding="utf-8")
    assert "env cannot weaken L1 proof requirement" in cfg
    assert "self.bridge_require_l1_proof = True" in cfg
    # apply_env_secrets must force True in production
    assert "Env cannot weaken prod L1-proof invariant" in cfg


def test_relayer_blind_confirm_prod_hard_fail():
    text = Path("scripts/bridge_relayer.py").read_text(encoding="utf-8")
    assert "refusing --allow-blind-confirm against prod API" in text
    assert "deployment_mode" in text


def test_light_client_rejects_unanchored_peer_bootstrap():
    from light.light_client import LightClient
    from core.block_header import BlockHeader

    lc = LightClient()
    assert lc.get_stats()["trust_mode"] == "unanchored"
    assert lc.get_stats()["peer_import_requires_trusted_anchor"] is True
    # Empty client must not bootstrap trust from peer headers.
    hdr = BlockHeader(
        number=1,
        parent_hash="0" * 64,
        proposer="0xabc",
        state_root="1" * 64,
        tx_root="2" * 64,
        timestamp=1,
        extra_data="",
    )
    assert lc.sync_headers_from_peers([hdr.to_dict()]) == 0
    assert lc.get_stats()["peer_import_rejected"] >= 1
    assert lc.get_header_count() == 0


def test_pbs_not_mev_protection():
    from consensus.pbs import PBSMarket, Builder, Proposer

    market = PBSMarket()
    market.add_builder(Builder("b1"))
    market.add_proposer(Proposer("p1"))
    txs = [{"hash": "a", "gas_price": 10}, {"hash": "b", "gas_price": 20}]
    result = market.run_auction(txs)
    assert result is not None
    assert result["mev_protection"] is False
    assert result["ordering_applied"] is False
    assert result["simulation_only"] is True
    assert [t["hash"] for t in result["transactions"]] == ["a", "b"]
    main = Path("main.py").read_text(encoding="utf-8")
    assert "PBS auction (MEV protection)" not in main
    assert "PBS handles protection" not in main


def test_ai_validator_gated_and_honest():
    cfg = Path("runtime/config.py").read_text(encoding="utf-8")
    assert "FEATURE_AI_VALIDATOR" in cfg
    main = Path("main.py").read_text(encoding="utf-8")
    assert "feature_ai_validator" in main
    assert "consensus_wired=false" in main
    ai = Path("features/ai_validator.py").read_text(encoding="utf-8")
    # detect_mev_opportunity must not invent numbers via random.uniform
    start = ai.find("def detect_mev_opportunity")
    end = ai.find("\n    def ", start + 1)
    body = ai[start:end] if start >= 0 else ""
    assert "random.uniform" not in body
    assert "consensus_wired" in ai
    assert "model_bound" in ai
    from features.ai_validator import AIValidatorEngine

    eng = AIValidatorEngine()
    stats = eng.get_stats()
    assert stats["simulation_only"] is True
    assert stats["consensus_wired"] is False
    assert stats["model_bound"] is False
    mev = eng.detect_mev_opportunity([1, 2, 3, 4])
    assert mev["invented_numbers"] is False
    for opp in mev["opportunities"]:
        assert opp.get("profit") is None
        assert opp.get("probability") is None
    http = Path("api/http.py").read_text(encoding="utf-8")
    assert '"consensus_wired": False' in http
    assert '"model_bound": False' in http
