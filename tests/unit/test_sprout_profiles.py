#!/usr/bin/env python3
"""Industrial L1 EVM depth — mesh profile invariants (ADR 0016 Profile A)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_prod_mesh_evm_inside_core_not_minivm() -> None:
    for name in ("node.prod.mesh1.json", "node.prod.mesh2.json", "node.prod.mesh3.json"):
        data = json.loads((ROOT / "docker" / name).read_text(encoding="utf-8"))
        assert data.get("evm_create2_eip1014") is True
        assert data.get("evm_require_deploy_salt") is True
        assert data.get("feature_minivm") is False
        assert data.get("feature_wasm") is False
        assert int(data.get("chain_apply_queue_max", 0)) >= 1
        assert int(data.get("tip_ancestry_window_max", 0)) >= 1


def test_staging_app_chain_id_not_prod_mesh() -> None:
    data = json.loads((ROOT / "docker" / "node.staging.app.json").read_text(encoding="utf-8"))
    assert int(data["chain_id"]) == 778889
    assert data["feature_nft"] is True
    assert data["feature_sharding"] is False
    assert data["deployment_mode"] == "staging"


def test_sandbox_l2_aux_features_isolated() -> None:
    data = json.loads((ROOT / "docker" / "node.sandbox.l2.json").read_text(encoding="utf-8"))
    assert int(data["chain_id"]) == 778890
    assert data["feature_plasma"] is True
    assert data["feature_lightning"] is True
    assert data["feature_wasm"] is True
    assert data["feature_nft"] is False
    assert data["bridge_enabled"] is False
