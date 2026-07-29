#!/usr/bin/env python3
"""Unit DoD + fault-injection stress tests for storage ports (ADR 0006 C)."""

from __future__ import annotations

import ast
import sys
import threading
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
from tests.unit.fakes.fake_storage import (
    COMMIT_FAULT_DISK_FULL,
    COMMIT_FAULT_ENOSPC_MID,
    COMMIT_FAULT_IO,
    FakeStorage,
)


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
    txs: list | None = None,
) -> None:
    uow = store.begin_block_commit(
        expected_parent=expected_parent or parent,
        expected_tip_height=expected_tip_height,
    )
    blk = _block(height, hh, parent)
    uow.write_block(blk)
    if txs:
        uow.write_transactions(txs)
    if accounts:
        uow.write_state_delta(accounts)
    uow.set_tip(TipMeta(height=height, head_hash=hh, state_root=f"root-{height}"))
    uow.commit()


def _snapshot(store: FakeStorage) -> dict:
    return {
        "tip_h": store.tip_height(),
        "tip_hash": store.tip_hash(),
        "counts": store.snapshot_counts(),
        "state_root": store.get_state_root(),
        "alice": store.get_account("alice"),
        "bob": store.get_account("bob"),
    }


# ── Atomicity (baseline DoD) ─────────────────────────────────────────────────


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
    uow.commit()
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


# ── Disk / integrity faults (baseline DoD) ───────────────────────────────────


def test_disk_full_on_commit_raises_and_tip_unchanged() -> None:
    store = FakeStorage()
    _commit_one(store, height=1, hh="h1", expected_tip_height=0)
    store.inject_commit_fault(COMMIT_FAULT_DISK_FULL)
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
    store.inject_block_corruption("bad_hash")
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
    uow.commit()
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
    store.inject_commit_fault(COMMIT_FAULT_IO)
    uow = store.begin_block_commit(expected_tip_height=0)
    uow.write_block(_block(1, "h1"))
    with pytest.raises(StorageUnavailableError):
        uow.commit()
    assert store.tip_height() == 0


# ── Stress: ENOSPC mid-write → full rollback ─────────────────────────────────


def test_enospc_mid_write_rolls_back_no_partial_block_or_state() -> None:
    """ENOSPC mid WriteBatch: tip, body, accounts must remain pre-commit snapshot."""
    store = FakeStorage()
    _commit_one(
        store,
        height=1,
        hh="canon_1",
        accounts={"alice": {"balance_satoshi": 50, "nonce": 1}},
        expected_tip_height=0,
    )
    store.set_finalized_height(1)
    before = _snapshot(store)

    store.inject_commit_fault(COMMIT_FAULT_ENOSPC_MID)
    uow = store.begin_block_commit(expected_parent="canon_1", expected_tip_height=1)
    uow.write_block(_block(2, "partial_2", "canon_1"))
    uow.write_transactions([{"hash": "tx_partial", "from": "alice", "to": "bob"}])
    uow.write_state_delta(
        {
            "alice": {"balance_satoshi": 10, "nonce": 2},
            "bob": {"balance_satoshi": 40, "nonce": 0},
        }
    )
    uow.set_tip(TipMeta(height=2, head_hash="partial_2", state_root="root-partial"))

    with pytest.raises(StorageFullError) as ei:
        uow.commit()
    assert ei.value.reason_code == "disk_full"
    assert "ENOSPC" in str(ei.value) or "space" in str(ei.value).lower()

    after = _snapshot(store)
    assert after["tip_h"] == before["tip_h"] == 1
    assert after["tip_hash"] == before["tip_hash"] == "canon_1"
    assert after["state_root"] == before["state_root"] == "root-1"
    assert store.get_by_hash("partial_2") is None
    assert store.get_by_height(2) is None
    assert store.get_account("bob") is None
    alice = store.get_account("alice")
    assert alice is not None and alice.balance_satoshi == 50
    assert store.finalized_height() == 1
    assert store.last_flush_ok() is False
    assert store.snapshot_counts()["enospc_aborts"] == 1
    assert store.snapshot_counts()["heights"] == 1


def test_enospc_then_recover_commit_succeeds_cleanly() -> None:
    store = FakeStorage()
    _commit_one(store, height=1, hh="h1", expected_tip_height=0)
    store.inject_commit_fault(COMMIT_FAULT_ENOSPC_MID)
    uow = store.begin_block_commit(expected_parent="h1", expected_tip_height=1)
    uow.write_block(_block(2, "h2", "h1"))
    uow.write_state_delta({"bob": {"balance_satoshi": 7}})
    uow.set_tip(TipMeta(height=2, head_hash="h2", state_root="root-2"))
    with pytest.raises(StorageFullError):
        uow.commit()

    # Retry without fault — full atomic success.
    _commit_one(
        store,
        height=2,
        hh="h2",
        parent="h1",
        expected_parent="h1",
        expected_tip_height=1,
        accounts={"bob": {"balance_satoshi": 7}},
    )
    assert store.tip_height() == 2
    assert store.tip_hash() == "h2"
    assert store.get_account("bob") is not None
    assert store.last_flush_ok() is True


# ── Stress: crash reopen + tip repair ────────────────────────────────────────


def test_crash_reopen_tip_repair_rewinds_orphan_head_and_finalized() -> None:
    """Tip points past missing body → repair restores head + finalized pointers."""
    store = FakeStorage()
    _commit_one(store, height=1, hh="final_1", expected_tip_height=0)
    _commit_one(
        store,
        height=2,
        hh="final_2",
        parent="final_1",
        expected_parent="final_1",
        expected_tip_height=1,
        accounts={"alice": {"balance_satoshi": 1}},
    )
    store.set_finalized_height(2)

    # Simulate crash: tip meta advanced to #3 but body never landed.
    store.inject_tip_orphan(height=3, head_hash="ghost_3")
    store.set_finalized_height(3)
    assert store.tip_height() == 3
    assert store.get_by_height(3) is None

    recovered = store.reopen_after_crash()
    assert recovered.tip_height() == 2
    assert recovered.tip_hash() == "final_2"
    assert recovered.get_by_hash("ghost_3") is None
    assert recovered.get_by_height(2) is not None
    assert recovered.finalized_height() == 2
    assert recovered.last_flush_ok() is True


def test_crash_mid_commit_interrupt_then_reopen_keeps_prior_tip() -> None:
    store = FakeStorage()
    _commit_one(store, height=1, hh="alive", expected_tip_height=0)
    store.set_finalized_height(1)
    store.interrupt_next_commit = True
    uow = store.begin_block_commit(expected_parent="alive", expected_tip_height=1)
    uow.write_block(_block(2, "dead", "alive"))
    uow.write_state_delta({"x": {"balance_satoshi": 99}})
    uow.set_tip(TipMeta(height=2, head_hash="dead"))
    uow.commit()

    recovered = store.reopen_after_crash()
    assert recovered.tip_height() == 1
    assert recovered.tip_hash() == "alive"
    assert recovered.finalized_height() == 1
    assert recovered.get_account("x") is None


def test_tip_repair_walks_down_multiple_missing_heights() -> None:
    store = FakeStorage()
    _commit_one(store, height=1, hh="h1", expected_tip_height=0)
    store.set_finalized_height(1)
    # Tip jumped to 5 with bodies 2..5 missing.
    store.inject_tip_orphan(height=5, head_hash="ghost5")
    store.set_finalized_height(5)
    store.repair_tip_consistency()
    assert store.tip_height() == 1
    assert store.tip_hash() == "h1"
    assert store.finalized_height() == 1


# ── Stress: CAS concurrent parent conflict ───────────────────────────────────


def test_cas_conflict_concurrent_uow_conflicting_parent_hash() -> None:
    """Two UoWs race: first wins; second with stale/conflict parent fails CAS."""
    store = FakeStorage()
    _commit_one(store, height=1, hh="parent_a", expected_tip_height=0)

    # Contender A and B both expect parent_a at tip=1.
    uow_a = store.begin_block_commit(expected_parent="parent_a", expected_tip_height=1)
    uow_b = store.begin_block_commit(expected_parent="parent_a", expected_tip_height=1)

    uow_a.write_block(_block(2, "child_a", "parent_a"))
    uow_a.write_state_delta({"alice": {"balance_satoshi": 11}})
    uow_a.set_tip(TipMeta(height=2, head_hash="child_a", state_root="root-a"))

    uow_b.write_block(_block(2, "child_b", "parent_a"))
    uow_b.write_state_delta({"bob": {"balance_satoshi": 22}})
    uow_b.set_tip(TipMeta(height=2, head_hash="child_b", state_root="root-b"))

    uow_a.commit()
    assert store.tip_hash() == "child_a"

    with pytest.raises(StorageConflictError) as ei:
        uow_b.commit()
    assert ei.value.reason_code in ("expected_parent_mismatch", "stale_tip_height")
    assert store.tip_height() == 2
    assert store.tip_hash() == "child_a"
    assert store.get_by_hash("child_b") is None
    assert store.get_account("bob") is None
    assert store.get_account("alice") is not None


def test_cas_conflict_wrong_parent_hash_does_not_mutate() -> None:
    store = FakeStorage()
    _commit_one(store, height=1, hh="real_parent", expected_tip_height=0)
    before = store.snapshot_counts()
    uow = store.begin_block_commit(
        expected_parent="other_fork_parent",
        expected_tip_height=1,
    )
    uow.write_block(_block(2, "evil", "other_fork_parent"))
    uow.set_tip(TipMeta(height=2, head_hash="evil"))
    with pytest.raises(StorageConflictError) as ei:
        uow.commit()
    assert ei.value.reason_code == "expected_parent_mismatch"
    assert store.snapshot_counts()["heights"] == before["heights"]
    assert store.tip_hash() == "real_parent"


def test_cas_threaded_race_only_one_child_commits() -> None:
    store = FakeStorage()
    _commit_one(store, height=1, hh="p", expected_tip_height=0)
    errors: list[BaseException] = []
    wins: list[str] = []

    def _race(name: str) -> None:
        try:
            uow = store.begin_block_commit(expected_parent="p", expected_tip_height=1)
            uow.write_block(_block(2, name, "p"))
            uow.set_tip(TipMeta(height=2, head_hash=name))
            uow.commit()
            wins.append(name)
        except BaseException as exc:  # noqa: BLE001 — collect for assertion
            errors.append(exc)

    t1 = threading.Thread(target=_race, args=("child_left",))
    t2 = threading.Thread(target=_race, args=("child_right",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(wins) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], StorageConflictError)
    assert store.tip_height() == 2
    assert store.tip_hash() in ("child_left", "child_right")
    assert store.get_by_hash("child_left") is None or store.get_by_hash("child_right") is None
    assert (store.get_by_hash("child_left") is not None) ^ (
        store.get_by_hash("child_right") is not None
    )


# ── Extra integrity ──────────────────────────────────────────────────────────


def test_corrupt_account_read_raises_no_empty_dict() -> None:
    store = FakeStorage()
    _commit_one(
        store,
        height=1,
        hh="h1",
        accounts={"alice": {"balance_satoshi": 9}},
        expected_tip_height=0,
    )
    store.inject_account_corruption("alice")
    with pytest.raises(StorageCorruptionError):
        store.get_account("alice")


def test_account_record_roundtrip_via_state_delta() -> None:
    store = FakeStorage()
    rec = AccountRecord(address="Carol", balance_satoshi=123, nonce=3, code="0xab")
    uow = store.begin_block_commit(expected_tip_height=0)
    uow.write_block(_block(1, "h1"))
    uow.write_state_delta([rec])
    uow.set_tip(TipMeta(height=1, head_hash="h1"))
    uow.commit()
    got = store.get_account("carol")
    assert got is not None
    assert got.balance_satoshi == 123
    assert got.nonce == 3


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


def test_rocks_adapter_maps_corruption_and_disk_full_messages() -> None:
    from storage.adapters.rocks_adapter import map_engine_error

    assert isinstance(
        map_engine_error(RuntimeError("RocksDB: Corruption: checksum mismatch")),
        StorageCorruptionError,
    )
    assert isinstance(
        map_engine_error(OSError("No space left on device")),
        StorageFullError,
    )
    assert isinstance(
        map_engine_error(IOError("engine closed")),
        StorageUnavailableError,
    )
