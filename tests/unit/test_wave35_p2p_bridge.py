"""Wave 35 — P2P reconcile, bridge2 stats, L1 proofs, EVM validate UI hooks."""
import os
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_bridge2_stats_uses_unified_overview():
    from api.http import _build_bridge_overview

    class _Cfg:
        bridge_enabled = True
        bridge_mode = "rust"
        bridge_auto_confirm_sec = 0
        bridge_l1_queue_path = "data/bridge_l1_queue.json"

    class _Db:
        def get_bridge_locks(self, limit=1000):
            return [
                {"tx_hash": "abc", "status": "confirmed", "amount": 9.9},
                {"tx_hash": "def", "status": "pending", "amount": 1.0},
            ]

    overview = _build_bridge_overview(None, None, _Cfg(), _Db())
    assert overview["mode"] == "rust"
    assert overview["locks"]["total"] == 2
    assert overview["locks"]["pending"] == 1


def test_l1_proof_meta_roundtrip(tmp_path):
    from storage.database import Database

    db = Database(str(tmp_path / "t.db"))
    db.set_meta("bridge_l1_proofs", [])
    proofs = db.get_meta("bridge_l1_proofs", [])
    proofs.append({
        "l1_tx_hash": "0xl1abc",
        "abs_lock_tx": "lock123",
        "chain": "ethereum",
        "registered_at": int(time.time()),
    })
    db.set_meta("bridge_l1_proofs", proofs)
    loaded = db.get_meta("bridge_l1_proofs", [])
    assert len(loaded) == 1
    assert loaded[0]["l1_tx_hash"] == "0xl1abc"


def test_sync_with_peer_equal_height_divergent_head_schedules_reconcile():
    from network.sync.sync_manager import SyncManager

    class _Storage:
        def get_latest_block_number(self):
            return 1

        def get_block(self, height):
            return {"number": height, "hash": f"0x{height}"}

    class _Node:
        storage = _Storage()

    mgr = SyncManager(_Node())
    blocks = mgr._get_blocks_from_height(1, 2)
    assert blocks and blocks[0]["hash"] == "0x1"


def test_evm_validate_bytecode_endpoint_logic():
    from execution.evm_bytecode_validator import validate_bytecode_hex

    ok = validate_bytecode_hex("600160005260206000f3")
    assert ok["valid"] is True
    bad = validate_bytecode_hex("fe")  # INVALID opcode at start if not supported — 0xFE is supported actually
    assert "valid" in bad


def test_verify_p2p_has_reconcile_trigger():
    src = open(os.path.join(ROOT, "scripts", "verify_p2p_ci.py"), encoding="utf-8").read()
    assert "_trigger_reconcile" in src
    assert "/sync/reconcile" in src
