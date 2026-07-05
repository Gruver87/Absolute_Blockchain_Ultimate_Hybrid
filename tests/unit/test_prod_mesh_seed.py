#!/usr/bin/env python3
"""Seed follower DB clone for prod-mesh3 spawn."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.ceremony_keygen import generate_validator_set
from runtime.prod_smoke_profile import write_prod_mesh3_configs
from storage.chain_clone import clone_chain_data
from storage.database import Database


def test_seed_follower_clones_chainstore(tmp_path):
    template = {
        "version": 1,
        "validators": [
            {"index": 1, "node_id": "v1", "address": "0x1", "mines": True, "stake": 5000},
            {"index": 2, "node_id": "v2", "address": "0x2", "mines": False, "stake": 3000},
            {"index": 3, "node_id": "v3", "address": "0x3", "mines": False, "stake": 2000},
        ],
    }
    template_path = tmp_path / "template.json"
    template_path.write_text(json.dumps(template), encoding="utf-8")
    ceremony_dir = tmp_path / "ceremony"
    generate_validator_set(str(template_path), str(ceremony_dir))

    mesh_tmp = tmp_path / "mesh"
    cfg1, cfg2, cfg3, _, _, _ = write_prod_mesh3_configs(
        str(mesh_tmp),
        ceremony_dir=str(ceremony_dir),
    )

    def data_dir(cfg_path: str):
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
        db_path = __import__("pathlib").Path(cfg["db_path"])
        return db_path.parent

    with open(cfg1, encoding="utf-8") as f:
        leader_cfg = json.load(f)
    leader = data_dir(cfg1)
    leader.mkdir(parents=True, exist_ok=True)
    db_path = leader_cfg["db_path"]
    if not os.path.isabs(db_path):
        db_path = str(leader / os.path.basename(db_path))
    if leader_cfg.get("db_engine") == "rocksdb":
        pytest.importorskip("abs_native")
        if not hasattr(__import__("abs_native"), "RocksEngine"):
            pytest.skip("RocksEngine not built")
        from storage.rocks_store import RocksChainStore

        db = RocksChainStore(db_path)
        db.initialize()
        db.save_block({"height": 0, "hash": "0" * 64, "miner": "genesis", "transactions": []})
        db.close()
        expected_engine = "rocksdb"
    else:
        db = Database(db_path)
        db.initialize()
        db.save_block({"height": 0, "hash": "0" * 64, "miner": "genesis", "transactions": []})
        db.close()
        expected_engine = "sqlite"

    follower = data_dir(cfg2)
    engine = clone_chain_data(str(leader), str(follower))
    assert engine == expected_engine
    if expected_engine == "rocksdb":
        from storage.rocks_store import RocksChainStore

        restored = RocksChainStore(str(follower / "chainstore"))
        restored.initialize()
        assert restored.get_chain_tip() == 0
        restored.close()
    else:
        restored = Database(str(follower / "chain.db"))
        restored.initialize()
        assert restored.get_chain_tip() == 0
        restored.close()
