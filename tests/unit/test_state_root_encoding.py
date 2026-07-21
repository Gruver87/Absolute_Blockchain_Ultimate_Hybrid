"""State-root encoding version scaffold."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_active_encoding_is_v1_float_contract():
    from runtime.state_root_encoding import active_state_root_encoding

    enc = active_state_root_encoding()
    assert enc["version"] == 1
    assert enc["name"] == "float_b_round12"
    assert enc["active"] is True
    assert enc["satoshi_tip_ready"] is False


def test_v2_request_blocked_without_migration():
    from runtime.config import Config
    from runtime.state_root_encoding import active_state_root_encoding

    cfg = Config()
    cfg.state_root_encoding_version = 2
    enc = active_state_root_encoding(cfg)
    assert enc["version"] == 2
    assert enc["active"] is False
    assert "blocked_reason" in enc


def test_blockchain_policy_includes_encoding(tmp_path):
    import os
    import tempfile

    from runtime.config import Config
    from storage.database import Database
    from core.blockchain import Blockchain

    fd, path = tempfile.mkstemp(suffix=".db", dir=tmp_path)
    os.close(fd)
    cfg = Config()
    cfg.db_path = path
    db = Database(path)
    db.initialize()
    bc = Blockchain(cfg, db)
    policy = bc.get_state_root_policy()
    assert policy["encoding"]["active"]["version"] == 1
    db.close()
    os.remove(path)
