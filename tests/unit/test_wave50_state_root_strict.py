"""Wave 50 — strict state_root on P2P import."""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)


def _make_chain():
    from runtime.config import Config
    from storage.database import Database
    from kernel.event_bus import EventBus
    from core.blockchain import Blockchain

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    cfg = Config()
    cfg.db_path = path
    cfg.miner_address = "0x" + "a" * 40
    cfg.verify_peer_state_root = True
    cfg.state_root_strict_p2p = True
    db = Database(path)
    db.initialize()
    bc = Blockchain(cfg, db, EventBus())
    return cfg, db, bc, path


def test_strict_p2p_rejects_mismatch_above_baseline():
    from core.blockchain import Block

    cfg, db, bc, path = _make_chain()
    try:
        for _ in range(3):
            assert bc.add_block(bc.create_block([], cfg.miner_address))
        baseline = bc.get_height()
        bc.set_state_root_baseline(baseline)

        nxt = bc.create_block([], cfg.miner_address)
        bad_blk = Block(
            height=nxt.height,
            parent_hash=nxt.parent_hash,
            miner=nxt.miner,
            transactions=nxt.transactions,
            timestamp=nxt.timestamp,
            extra_data=nxt.extra_data,
            state_root="f" * 64,
        )
        bad = bad_blk.to_dict()
        bad["hash"] = bad_blk._compute_hash()

        assert bc.import_block(bad) is False
        rows = db.get_state_root_mismatches(limit=5)
        assert len(rows) >= 1
        assert rows[0]["height"] == bad["height"]
    finally:
        db.close()
        os.remove(path)


def test_legacy_p2p_rejects_inconsistent_peer_hash():
    cfg, db, bc, path = _make_chain()
    try:
        cfg.state_root_strict_p2p = False
        for _ in range(3):
            assert bc.add_block(bc.create_block([], cfg.miner_address))
        bc.set_state_root_baseline(bc.get_height())

        nxt = bc.create_block([], cfg.miner_address)
        drift = nxt.to_dict()
        drift["state_root"] = "f" * 64
        drift["hash"] = "c" * 64

        assert bc.import_block(drift) is False
    finally:
        db.close()
        os.remove(path)


def test_state_root_policy_fields():
    cfg, db, bc, path = _make_chain()
    try:
        bc.set_state_root_baseline(10)
        pol = bc.get_state_root_policy()
        assert pol["state_root_strict_p2p"] is True
        assert pol["policy"] == "strict_p2p"
        assert pol["baseline_height"] == 10
        assert bc._state_root_check_mode(11, "a" * 64, True) == "strict"
        assert bc._state_root_check_mode(10, "a" * 64, True) == "legacy_warn"
    finally:
        db.close()
        os.remove(path)
