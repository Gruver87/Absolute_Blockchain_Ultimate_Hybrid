#!/usr/bin/env python3
"""Genesis founder must stay pinned for state replay (mesh followers)."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.config import Config
from storage.database import Database
from kernel.event_bus import EventBus
from core.blockchain import Blockchain, Block


def test_reorg_uses_genesis_founder_meta_not_runtime_wallet(tmp_path):
    founder = "0x" + "11" * 20
    wrong_wallet = "0x" + "22" * 20

    cfg = Config()
    cfg.db_path = str(tmp_path / "chain.db")
    cfg.miner_address = founder
    cfg.founder_address = founder
    db = Database(cfg.db_path)
    db.initialize()
    bc = Blockchain(cfg, db, EventBus())
    assert bc.add_block(bc.create_block([], founder))
    assert db.get_meta("genesis_founder") == founder
    expected_root = db.get_block(1)["state_root"]

    cfg.founder_address = wrong_wallet
    corrupt = dict(db.get_block(1))
    corrupt["state_root"] = db.get_block(0)["state_root"]
    corrupt["hash"] = Block.from_dict(corrupt)._compute_hash()
    db.save_block(corrupt)

    assert bc.ensure_state_at_tip()
    assert db.get_block(1)["state_root"] == expected_root


def test_manifest_founder_address_index_one(tmp_path):
    from runtime.validator_loader import manifest_founder_address

    manifest = {
        "validators": [
            {"index": 1, "address": "0x" + "aa" * 20},
            {"index": 2, "address": "0x" + "bb" * 20},
        ]
    }
    path = tmp_path / "m.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert manifest_founder_address(str(path)) == "0x" + "aa" * 20
