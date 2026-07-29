#!/usr/bin/env python3
"""Unit DoD for storage ports + FakeStorage (ADR 0006 A–C)."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from storage.types import (
    AccountRecord,
    BlockRecord,
    StorageConflictError,
    StorageCorruptionError,
    StorageFullError,
    StorageUnavailableError,
    TipMeta,
)
from tests.unit.fakes.fake_storage import FakeStorage


def _block(height: int, hh: str, parent: str = "") -> BlockRecord:
    return BlockRecord(
        height=height,
        block_hash=hh,
        parent_hash=parent,
        payload={"height": height, "hash": hh, "parent_hash": parent},
    )


def _commit_one(
    store: FakeStorage,
    *,
    height: int,
    hh: str,
    parent: str = "",
    accounts: dict | None = None,
    expected_parent: str = "",
    expected_tip_height: int = -1,
) -> None:
    uow = store.begin_block_commit(
        expected_parent=expected_parent or parent,
        expected_tip_height=expected_tip_height,
    )
    blk = _block(height, hh, parent)
    uow.write_block(blk)
    if accounts:
        uow.write_state_delta(accounts)
    uow.set_tip(TipMeta(height=height, head_hash=hh, state_root=f"root-{height}"))
    uow.commit()


# ── Atomicity ────────────────────────────────────────────────────────────────


def test_happy_path_commit_shows_tip_body_state_together() -> None:
    store = FakeStorage()
    acc = {"alice": {"balance_satoshi": 100, "nonce": 1}}
    _commit_one(
        store,
        height=1,
        hh="hash_1",
        parent="",
        accounts=acc,
        expected_tip_height=0,
    )
    assert store.tip_height() == 1
    assert store.tip_hash() == "hash_1"
    assert store.get_by_hash("hash_1") is not None
    assert store.get_by_height(1) is not None
    got = store.get_account("alice")
    assert got is not None
    assert got.balance_satoshi == 100
    assert store.get_state_root() == "root-1"


def test_abort_mid_uow_leaves_tip_unchanged() -> None:
    store = FakeStorage()
    _commit_one(store, height=1, hh="hash_1", expected_tip_height=0)
    uow = store.begin_block_commit(expected_parent="hash_1", expected_tip_height=1)
    uow.write_block(_block(2, "hash_2", "hash_1"))
    uow.write_state_delta({"bob": {"balance_satoshi": 5}})
    uow.set_tip(TipMeta(height=2, head_hash="hash_2"))
    uow.abort()
    assert store.tip_height() == 1
    assert store.tip_hash() == "hash_1"
    assert store.get_by_hash("hash_2") is None
    assert store.get_account("bob") is None


def test_interrupted_commit_reopen_recovers_last_committed_only() -> None:
    store = FakeStorage()
    _commit_one(store, height=1, hh="hash_1", expected_tip_height=0)
    store.interrupt_next_commit = True
    uow = store.begin_block_commit(expected_parent="hash_1", expected_tip_height=1)
    uow.write_block(_block(2, "hash_2", "hash_1"))
    uow.set_tip(TipMeta(height=2, head_hash="hash_2"))
    uow.commit()  # simulated crash — no durable mutation
    assert store.tip_height() == 1
    recovered = store.reopen_after_crash()
    assert recovered.tip_height() == 1
    assert recovered.tip_hash() == "hash_1"
    assert recovered.get_by_hash("hash_2") is None


def test_reorg_truncate_above_rewinds_tip() -> None:
    store = FakeStorage()
    _commit_one(store, height=1, hh="h1", expected_tip_height=0)
    _commit_one(
        store, height=2, hh="h2", parent="h1", expected_parent="h1", expected_tip_height=1
    )
    _commit_one(
        store, height=3, hh="h3", parent="h2", expected_parent="h2", expected_tip_height=2
    )
    store.reorg_truncate_above(1)
    assert store.tip_height() == 1
    assert store.tip_hash() == "h1"
    assert store.get_by_height(2) is None
    assert store.get_by_height(3) is None
    assert store.get_by_hash("h2") is None
    # Account policy for A–C fake: accounts are not auto-rewound (documented).
    # Tip/body/indexes above H are gone.


# ── Disk / integrity faults ──────────────────────────────────────────────────


def test_disk_full_on_commit_raises_and_tip_unchanged() -> None:
    store = FakeStorage()
    _commit_one(store, height=1, hh="h1", expected_tip_height=0)
    store.fail_next_commit = "disk_full"
    uow = store.begin_block_commit(expected_parent="h1", expected_tip_height=1)
    uow.write_block(_block(2, "h2", "h1"))
    uow.set_tip(TipMeta(height=2, head_hash="h2"))
    with pytest.raises(StorageFullError) as ei:
        uow.commit()
    assert ei.value.reason_code == "disk_full"
    assert store.tip_height() == 1
    assert store.get_by_hash("h2") is None


def test_corrupt_payload_on_get_by_hash_raises() -> None:
    store = FakeStorage()
    _commit_one(store, height=1, hh="bad_hash", expected_tip_height=0)
    store.corrupt_block_hashes.add("bad_hash")
    with pytest.raises(StorageCorruptionError):
        store.get_by_hash("bad_hash")
    with pytest.raises(StorageCorruptionError):
        store.get_by_height(1)


def test_double_commit_same_hash_idempotent() -> None:
    store = FakeStorage()
    _commit_one(store, height=1, hh="same", expected_tip_height=0)
    uow = store.begin_block_commit(expected_parent="", expected_tip_height=1)
    uow.write_block(_block(1, "same", ""))
    uow.set_tip(TipMeta(height=1, head_hash="same"))
    uow.commit()  # idempotent skip
    assert store.tip_height() == 1
    assert len(store._by_hash) == 1


def test_stale_expected_parent_raises_conflict() -> None:
    store = FakeStorage()
    _commit_one(store, height=1, hh="h1", expected_tip_height=0)
    uow = store.begin_block_commit(expected_parent="stale_parent", expected_tip_height=1)
    uow.write_block(_block(2, "h2", "stale_parent"))
    uow.set_tip(TipMeta(height=2, head_hash="h2"))
    with pytest.raises(StorageConflictError) as ei:
        uow.commit()
    assert ei.value.reason_code == "expected_parent_mismatch"
    assert store.tip_height() == 1


def test_stale_tip_height_raises_conflict() -> None:
    store = FakeStorage()
    _commit_one(store, height=1, hh="h1", expected_tip_height=0)
    uow = store.begin_block_commit(expected_parent="h1", expected_tip_height=0)
    uow.write_block(_block(2, "h2", "h1"))
    with pytest.raises(StorageConflictError) as ei:
        uow.commit()
    assert ei.value.reason_code == "stale_tip_height"


def test_io_fault_raises_unavailable() -> None:
    store = FakeStorage()
    store.fail_next_commit = "io"
    uow = store.begin_block_commit(expected_tip_height=0)
    uow.write_block(_block(1, "h1"))
    with pytest.raises(StorageUnavailableError):
        uow.commit()
    assert store.tip_height() == 0


# ── Isolation needles ────────────────────────────────────────────────────────


_FORBIDDEN = ("rocksdb", "RocksEngine", "RocksWriteBatch", "column_family")


def _assert_source_clean(rel: str) -> None:
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    for needle in _FORBIDDEN:
        assert needle not in text, f"{rel} must not contain {needle!r}"
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mod = getattr(node, "module", None) or ""
            names = [
                (a.name if isinstance(node, ast.Import) else (mod or ""))
                for a in getattr(node, "names", [])
            ]
            blob = " ".join([mod] + names).lower()
            assert "rocksdb" not in blob
            assert "rocks_engine" not in blob


def test_ports_types_have_no_rocks_imports() -> None:
    _assert_source_clean("storage/ports.py")
    _assert_source_clean("storage/types.py")


def test_domain_facing_tests_use_ports_fake_only() -> None:
    """Domain DoD cases talk to FakeStorage ports — no native engine import."""
    import tests.unit.test_storage_ports as me

    tree = ast.parse(Path(me.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "rocks_engine" not in node.module.lower()
            assert node.module != "rocksdb"
            assert not node.module.startswith("storage.rocks")
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "rocksdb" not in alias.name.lower()
                assert "rocks_engine" not in alias.name.lower()
    store = FakeStorage()
    assert store.health.ping() is True
    assert store.blocks.tip_height() == 0


# ── Adapter unit (stub store — no native engine) ─────────────────────────────


def test_rocks_adapter_error_map_and_repair() -> None:
    from storage.adapters.rocks_adapter import RocksDBStorageAdapter, _map_engine_error

    err = _map_engine_error(OSError(28, "No space left on device"))
    assert isinstance(err, StorageFullError)

    class Stub:
        def __init__(self) -> None:
            self.tip = 2
            self.blocks = {1: {"height": 1, "hash": "h1", "parent_hash": ""}}
            self.truncated = []

        def get_chain_tip(self) -> int:
            return self.tip

        def get_block(self, h: int):
            return self.blocks.get(int(h))

        def get_last_block(self):
            return self.blocks.get(self.tip) or self.blocks.get(1)

        def get_block_by_hash(self, hh: str):
            for b in self.blocks.values():
                if b.get("hash") == hh:
                    return b
            return None

        def reorg_truncate_above(self, h: int) -> None:
            self.truncated.append(int(h))
            self.tip = int(h)
            self.blocks = {k: v for k, v in self.blocks.items() if k <= int(h)}

        def get_account(self, address: str):
            return None

    stub = Stub()
    adapter = RocksDBStorageAdapter(stub, fail_closed_repair=True, repair_on_open=True)
    assert stub.truncated == [1]
    assert adapter.tip_height() == 1
    assert adapter.ping() is True
