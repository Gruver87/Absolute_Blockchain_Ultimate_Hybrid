#!/usr/bin/env python3
"""Integration cutover: Blockchain canonical persist via StoragePort UoW (ADR 0006 D–E)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.blockchain import Block, Blockchain, Transaction
from kernel.event_bus import EventBus
from runtime.config import Config
from storage.adapters.rocks_adapter import RocksDBStorageAdapter
from storage.database import Database
from storage.factory import open_storage
from storage.types import StorageFullError, TipMeta


@pytest.fixture
def chain_env(tmp_path):
    cfg = Config()
    cfg.db_path = str(tmp_path / "cutover.db")
    cfg.burn_address = "0x" + "d" * 40
    db = Database(cfg.db_path)
    db.initialize()
    storage = open_storage(db, repair_on_open=True)
    bus = EventBus()
    bc = Blockchain(cfg, db, bus, storage=storage)
    return cfg, db, storage, bc


def _fund(bc: Blockchain, addr: str, amount: float = 100.0) -> None:
    bc.db.set_balance(addr, amount)


def _mine_one(bc: Blockchain, *, value: float = 1.0) -> Block:
    sender = "0x" + "a1" * 20
    recipient = "0x" + "b2" * 20
    _fund(bc, sender, 100.0)
    nonce = bc.db.get_nonce(sender)
    tx = Transaction(from_addr=sender, to_addr=recipient, value=value, nonce=int(nonce))
    block = bc.create_block([tx], proposer="0x" + "c3" * 20)
    assert bc.add_block(block)
    return block


# ── Happy path / spy ─────────────────────────────────────────────────────────


def test_add_block_uses_storage_uow_and_tip_body_visible(chain_env) -> None:
    _cfg, db, storage, bc = chain_env
    calls: List[dict] = []
    real_begin = storage.begin_block_commit

    def _spy_begin(*, expected_parent: str = "", expected_tip_height: int = -1):
        calls.append(
            {
                "expected_parent": expected_parent,
                "expected_tip_height": expected_tip_height,
            }
        )
        return real_begin(
            expected_parent=expected_parent,
            expected_tip_height=expected_tip_height,
        )

    storage.begin_block_commit = _spy_begin  # type: ignore[method-assign]

    block = _mine_one(bc)
    assert calls, "begin_block_commit must be used for canonical persist"
    assert calls[-1]["expected_tip_height"] == block.height - 1

    tip_h = bc.get_height()
    last = bc.get_last_block()
    body = bc.get_block(block.height)
    assert tip_h == block.height
    assert last is not None
    assert last["hash"] == block.hash
    assert body is not None
    assert body["hash"] == block.hash
    assert body.get("state_root")
    assert body["state_root"] == bc.get_state_root()
    assert storage.blocks.tip_height() == tip_h
    assert storage.blocks.has_hash(block.hash)


def test_import_block_path_replays_via_same_uow_seam(tmp_path) -> None:
    cfg_a = Config()
    cfg_a.db_path = str(tmp_path / "a.db")
    cfg_a.burn_address = "0x" + "d" * 40
    db_a = Database(cfg_a.db_path)
    db_a.initialize()
    node_a = Blockchain(cfg_a, db_a, EventBus(), storage=open_storage(db_a))

    sender = "0x" + "d4" * 20
    recv = "0x" + "e5" * 20
    node_a.db.set_balance(sender, 50.0)
    tx = Transaction(from_addr=sender, to_addr=recv, value=5.0, nonce=0)
    blk = node_a.create_block([tx], proposer="0x" + "f6" * 20)
    assert node_a.add_block(blk)
    exported = dict(node_a.db.get_block(blk.height))

    cfg_b = Config()
    cfg_b.db_path = str(tmp_path / "b.db")
    cfg_b.burn_address = cfg_a.burn_address
    db_b = Database(cfg_b.db_path)
    db_b.initialize()
    node_b = Blockchain(cfg_b, db_b, EventBus(), storage=open_storage(db_b))
    node_b.db.set_balance(sender, 50.0)

    parent = node_b.get_last_block()
    assert parent is not None
    exported["parent_hash"] = parent["hash"]
    exported["timestamp"] = int(parent["timestamp"]) + 1
    exported["hash"] = Block.from_dict(exported)._compute_hash()

    assert node_b.import_block(exported)
    assert node_b.get_height() == blk.height
    assert node_b.get_balance(recv) == 5.0
    assert node_b.get_last_block()["hash"] == exported["hash"]


# ── CAS / ENOSPC / atomic abort ──────────────────────────────────────────────


def test_cas_stale_parent_via_storage_uow_rejects(chain_env) -> None:
    _cfg, db, storage, bc = chain_env
    first = _mine_one(bc)
    tip_before = bc.get_height()
    tip_hash = bc.get_last_block()["hash"]

    real = bc._persist_canonical_via_storage

    def _bad_cas(block, tx_dicts, *, expected_parent, expected_tip_height):
        return real(
            block,
            tx_dicts,
            expected_parent="deadbeef" * 8,
            expected_tip_height=expected_tip_height,
        )

    bc._persist_canonical_via_storage = _bad_cas  # type: ignore[method-assign]

    sender = "0x" + "11" * 20
    _fund(bc, sender, 50.0)
    tx = Transaction(from_addr=sender, to_addr="0x" + "22" * 20, value=1.0, nonce=0)
    block = bc.create_block([tx], proposer="0x" + "33" * 20)
    assert bc.add_block(block) is False
    assert bc.get_height() == tip_before
    assert bc.get_last_block()["hash"] == tip_hash
    assert bc.get_block(first.height + 1) is None


def test_enospc_on_uow_commit_rolls_back_outer_atomic(chain_env) -> None:
    _cfg, db, storage, bc = chain_env
    _mine_one(bc)
    tip_before = bc.get_height()

    # Force pure Python apply so account deltas stay inside db.atomic()
    # (native writeback may commit mid-batch — pre-existing; not this cutover).
    bc._block_transactions_are_simple = lambda _txs: False  # type: ignore[method-assign]
    bc._block_transactions_are_all_evm = lambda _txs: False  # type: ignore[method-assign]
    bc._block_transactions_are_mixed = lambda _txs: False  # type: ignore[method-assign]

    class _BoomUoW:
        def write_block(self, block) -> None:
            return None

        def write_transactions(self, transactions) -> None:
            return None

        def set_tip(self, tip: TipMeta) -> None:
            return None

        def commit(self) -> None:
            raise StorageFullError(
                "ENOSPC: No space left on device", reason_code="disk_full"
            )

        def abort(self) -> None:
            return None

    storage.begin_block_commit = (  # type: ignore[method-assign]
        lambda *, expected_parent="", expected_tip_height=-1: _BoomUoW()
    )

    sender = "0x" + "44" * 20
    _fund(bc, sender, 80.0)
    bal_before = bc.get_balance(sender)
    tx = Transaction(from_addr=sender, to_addr="0x" + "55" * 20, value=2.0, nonce=0)
    block = bc.create_block([tx], proposer="0x" + "66" * 20)
    assert bc.add_block(block) is False
    assert bc.get_height() == tip_before
    assert bc.get_block(tip_before + 1) is None
    assert abs(bc.get_balance(sender) - bal_before) < 1e-9


def test_exception_before_uow_aborts_atomic_no_partial_block(chain_env) -> None:
    _cfg, db, storage, bc = chain_env
    _mine_one(bc)
    tip_before = bc.get_height()

    def _boom_root():
        raise RuntimeError("injected_pre_persist_failure")

    bc._compute_state_root_from_db = _boom_root  # type: ignore[method-assign]

    sender = "0x" + "77" * 20
    _fund(bc, sender, 60.0)
    tx = Transaction(from_addr=sender, to_addr="0x" + "88" * 20, value=1.0, nonce=0)
    block = bc.create_block([tx], proposer="0x" + "99" * 20)
    assert bc.add_block(block) is False
    assert bc.get_height() == tip_before
    assert bc.get_block(tip_before + 1) is None


# ── Tip-safety smoke + adapter join batch ────────────────────────────────────


def test_after_import_tip_reads_agree_for_tip_safety_resync(tmp_path) -> None:
    """tip_safety note_import_result reads get_height / last hash — must agree."""
    cfg = Config()
    cfg.db_path = str(tmp_path / "tip.db")
    cfg.burn_address = "0x" + "d" * 40
    db = Database(cfg.db_path)
    db.initialize()
    bc = Blockchain(cfg, db, EventBus(), storage=open_storage(db))
    block = _mine_one(bc)

    height = bc.get_height()
    last = bc.get_last_block()
    assert last is not None
    assert height == block.height
    assert last["hash"] == block.hash
    assert bc.get_block(height)["hash"] == last["hash"]
    assert bc.storage.blocks.tip_height() == height
    assert bc.storage.blocks.tip_hash() == last["hash"]


def test_adapter_joins_open_sqlite_transaction_without_nested_atomic(tmp_path) -> None:
    cfg = Config()
    cfg.db_path = str(tmp_path / "join.db")
    db = Database(cfg.db_path)
    db.initialize()
    # Seed tip body like genesis so CAS has a parent tip.
    db.save_block(
        {
            "height": 0,
            "hash": "genesis_join_hash",
            "parent_hash": "",
            "state_root": "r0",
            "timestamp": 1,
            "miner": "genesis",
            "transactions": [],
        }
    )
    adapter = RocksDBStorageAdapter(db, repair_on_open=False)

    nested_opens: List[str] = []
    real_atomic = db.atomic

    def _counting_atomic():
        nested_opens.append("atomic")
        return real_atomic()

    db.atomic = _counting_atomic  # type: ignore[method-assign]

    with real_atomic():
        assert adapter._store_batch_open() is True
        uow = adapter.begin_block_commit(
            expected_parent="genesis_join_hash",
            expected_tip_height=0,
        )
        blk = {
            "height": 1,
            "hash": "cutover_join_hash_002",
            "parent_hash": "genesis_join_hash",
            "state_root": "root",
            "timestamp": 2,
            "miner": "miner",
            "transactions": [],
        }
        uow.write_block(blk)
        uow.write_transactions([])
        uow.set_tip(TipMeta(height=1, head_hash=str(blk["hash"]), state_root="root"))
        uow.commit()

    assert nested_opens == [], "adapter must join open tx — no nested db.atomic()"
    assert db.get_block(1) is not None
    assert db.get_block(1)["hash"] == "cutover_join_hash_002"


def test_blockchain_auto_wires_storage_when_omitted(tmp_path) -> None:
    cfg = Config()
    cfg.db_path = str(tmp_path / "auto.db")
    cfg.burn_address = "0x" + "d" * 40
    db = Database(cfg.db_path)
    db.initialize()
    bc = Blockchain(cfg, db, EventBus())
    assert bc.storage is not None
    assert isinstance(bc.storage, RocksDBStorageAdapter)
    assert bc.storage.unwrap() is db
    block = _mine_one(bc)
    assert bc.get_height() == block.height


def test_blockchain_domain_has_no_self_db_attribute_access() -> None:
    """Wave F needle: domain logic must not use self.db.* (compat property only)."""
    path = ROOT / "core" / "blockchain.py"
    text = path.read_text(encoding="utf-8")
    offenders = [
        f"{i}:{line.strip()}"
        for i, line in enumerate(text.splitlines(), 1)
        if "self.db." in line or "hasattr(self.db" in line or "self.db," in line
    ]
    assert offenders == [], f"self.db still used in domain logic: {offenders}"
    assert "self.storage." in text
    assert "def db(self)" in text
    assert "@property" in text


def test_compat_db_property_unwraps_underlying_store(chain_env) -> None:
    _cfg, db, storage, bc = chain_env
    assert bc.db is db
    assert bc.storage.unwrap() is db
    bc.db.set_balance("0x" + "ab" * 20, 3.0)
    assert abs(bc.get_balance("0x" + "ab" * 20) - 3.0) < 1e-9
