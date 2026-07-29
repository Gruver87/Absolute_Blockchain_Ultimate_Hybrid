"""In-memory StoragePort façade for ADR 0006 unit tests."""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence

from storage.types import (
    AccountRecord,
    BlockRecord,
    StorageConflictError,
    StorageCorruptionError,
    StorageFullError,
    StorageUnavailableError,
    TipMeta,
)


class _FakeUoW:
    def __init__(
        self,
        store: "FakeStorage",
        *,
        expected_parent: str,
        expected_tip_height: int,
    ) -> None:
        self._store = store
        self._expected_parent = str(expected_parent or "")
        self._expected_tip_height = int(expected_tip_height)
        self._block: Optional[BlockRecord] = None
        self._txs: List[Mapping[str, Any]] = []
        self._accounts: Dict[str, AccountRecord] = {}
        self._tip: Optional[TipMeta] = None
        self._aborted = False
        self._committed = False

    def write_block(self, block: BlockRecord | Mapping[str, Any]) -> None:
        self._ensure_open()
        self._block = (
            block if isinstance(block, BlockRecord) else BlockRecord.from_mapping(block)
        )

    def write_transactions(self, transactions: Sequence[Mapping[str, Any]]) -> None:
        self._ensure_open()
        self._txs = [dict(t) for t in (transactions or ())]

    def write_state_delta(
        self,
        accounts: Sequence[AccountRecord] | Mapping[str, Mapping[str, Any]],
    ) -> None:
        self._ensure_open()
        if isinstance(accounts, Mapping):
            for addr, row in accounts.items():
                rec = (
                    row
                    if isinstance(row, AccountRecord)
                    else AccountRecord.from_mapping(str(addr), row)
                )
                self._accounts[rec.address] = rec
            return
        for row in accounts or ():
            rec = row if isinstance(row, AccountRecord) else AccountRecord.from_mapping(
                str(getattr(row, "address", "")), row  # type: ignore[arg-type]
            )
            self._accounts[rec.address] = rec

    def set_tip(self, tip: TipMeta) -> None:
        self._ensure_open()
        self._tip = tip

    def commit(self) -> None:
        self._ensure_open()
        store = self._store
        fault = store.fail_next_commit
        if fault == "disk_full":
            store.fail_next_commit = ""
            raise StorageFullError("disk full", reason_code="disk_full")
        if fault == "io":
            store.fail_next_commit = ""
            raise StorageUnavailableError("io error", reason_code="io")
        if fault == "corruption":
            store.fail_next_commit = ""
            raise StorageCorruptionError("commit corrupt", reason_code="corruption")

        # CAS: expected tip height / parent
        tip_h = store.tip_height()
        tip_hash = store.tip_hash()
        if self._expected_tip_height >= 0 and tip_h != self._expected_tip_height:
            raise StorageConflictError(
                f"stale tip height want={self._expected_tip_height} got={tip_h}",
                reason_code="stale_tip_height",
            )
        if self._expected_parent:
            if tip_h > 0 and tip_hash.lower() != self._expected_parent.lower():
                raise StorageConflictError(
                    "expected_parent mismatch",
                    reason_code="expected_parent_mismatch",
                )

        if self._block is None:
            raise StorageUnavailableError("no block staged", reason_code="empty_uow")

        # Idempotent same-hash skip
        if store.has_hash(self._block.block_hash):
            self._committed = True
            return

        if store.interrupt_next_commit:
            # Simulate crash: do not mutate committed snapshot.
            store.interrupt_next_commit = False
            store._crash_pending = True
            self._committed = True
            return

        # Apply atomically to committed maps
        blk = self._block
        store._by_height[blk.height] = blk
        store._by_hash[blk.block_hash] = blk
        store._txs[blk.block_hash] = list(self._txs)
        for addr, acc in self._accounts.items():
            store._accounts[addr] = acc
        tip = self._tip or TipMeta(
            height=blk.height, head_hash=blk.block_hash, state_root=store._state_root
        )
        store._tip = tip
        if tip.state_root:
            store._state_root = tip.state_root
        self._committed = True

    def abort(self) -> None:
        self._aborted = True
        self._block = None
        self._txs = []
        self._accounts = {}
        self._tip = None

    def _ensure_open(self) -> None:
        if self._aborted:
            raise StorageUnavailableError("uow aborted", reason_code="aborted")
        if self._committed:
            raise StorageUnavailableError("uow already committed", reason_code="committed")


class FakeStorage:
    """Implements StoragePort (+ nested ports) entirely in memory."""

    def __init__(self) -> None:
        self._by_height: Dict[int, BlockRecord] = {}
        self._by_hash: Dict[str, BlockRecord] = {}
        self._txs: Dict[str, List[Mapping[str, Any]]] = {}
        self._accounts: Dict[str, AccountRecord] = {}
        self._tip = TipMeta(height=0, head_hash="")
        self._state_root = ""
        self._state_root_baseline = 0
        self._validators: List[Mapping[str, Any]] = []
        self._checkpoints: Dict[int, Mapping[str, Any]] = {}
        self._flush_ok = True
        self._approx_size = 0
        # Fault injection
        self.fail_next_commit = ""
        self.interrupt_next_commit = False
        self._crash_pending = False
        self.corrupt_block_hashes: set[str] = set()

    # ── StoragePort composite ────────────────────────────────────────────────

    @property
    def blocks(self) -> "FakeStorage":
        return self

    @property
    def state(self) -> "FakeStorage":
        return self

    @property
    def meta(self) -> "FakeStorage":
        return self

    @property
    def health(self) -> "FakeStorage":
        return self

    def begin_block_commit(
        self,
        *,
        expected_parent: str = "",
        expected_tip_height: int = -1,
    ) -> _FakeUoW:
        return _FakeUoW(
            self,
            expected_parent=expected_parent,
            expected_tip_height=expected_tip_height,
        )

    # ── BlockStorePort ───────────────────────────────────────────────────────

    def tip_height(self) -> int:
        return int(self._tip.height)

    def tip_hash(self) -> str:
        return str(self._tip.head_hash or "")

    def has_hash(self, block_hash: str) -> bool:
        return str(block_hash or "").strip() in self._by_hash

    def get_by_height(self, height: int) -> Optional[BlockRecord]:
        blk = self._by_height.get(int(height))
        if blk is None:
            return None
        if blk.block_hash in self.corrupt_block_hashes:
            raise StorageCorruptionError(
                f"corrupt block height={height}", reason_code="corrupt_block"
            )
        return blk

    def get_by_hash(self, block_hash: str) -> Optional[BlockRecord]:
        key = str(block_hash or "").strip()
        if key in self.corrupt_block_hashes:
            raise StorageCorruptionError(
                f"corrupt block hash={key[:16]}", reason_code="corrupt_block"
            )
        return self._by_hash.get(key)

    def iterate_heights(self, from_height: int, to_height: int) -> Sequence[BlockRecord]:
        out: List[BlockRecord] = []
        for h in range(int(from_height), int(to_height) + 1):
            blk = self.get_by_height(h)
            if blk is not None:
                out.append(blk)
        return out

    def reorg_truncate_above(self, height: int) -> None:
        cut = int(height)
        for h in list(self._by_height.keys()):
            if int(h) > cut:
                blk = self._by_height.pop(h)
                self._by_hash.pop(blk.block_hash, None)
                self._txs.pop(blk.block_hash, None)
        if self._tip.height > cut:
            if cut <= 0:
                self._tip = TipMeta(height=0, head_hash="")
            else:
                tip_blk = self._by_height.get(cut)
                self._tip = TipMeta(
                    height=cut,
                    head_hash=tip_blk.block_hash if tip_blk else "",
                    state_root=self._state_root,
                )

    # ── StateStorePort ───────────────────────────────────────────────────────

    def get_account(self, address: str) -> Optional[AccountRecord]:
        return self._accounts.get(str(address or "").strip().lower())

    def get_state_root(self) -> str:
        return str(self._state_root or "")

    def get_state_root_baseline(self) -> int:
        return int(self._state_root_baseline)

    def set_state_root_baseline(self, height: int) -> None:
        self._state_root_baseline = int(height)

    # ── MetaStorePort ────────────────────────────────────────────────────────

    def get_validators(self) -> Sequence[Mapping[str, Any]]:
        return list(self._validators)

    def get_checkpoint(self, epoch: int) -> Optional[Mapping[str, Any]]:
        return self._checkpoints.get(int(epoch))

    def put_checkpoint(self, epoch: int, data: Mapping[str, Any]) -> None:
        self._checkpoints[int(epoch)] = dict(data)

    # ── StorageHealthPort ────────────────────────────────────────────────────

    def ping(self) -> bool:
        return True

    def approximate_size(self) -> int:
        return int(self._approx_size) + len(self._by_hash) + len(self._accounts)

    def last_flush_ok(self) -> bool:
        return bool(self._flush_ok)

    # ── Crash recovery helper for tests ──────────────────────────────────────

    def reopen_after_crash(self) -> "FakeStorage":
        """Return a clone of last committed state (interrupted commit discarded)."""
        clone = FakeStorage()
        clone._by_height = copy.deepcopy(self._by_height)
        clone._by_hash = copy.deepcopy(self._by_hash)
        clone._txs = copy.deepcopy(self._txs)
        clone._accounts = copy.deepcopy(self._accounts)
        clone._tip = TipMeta(
            height=self._tip.height,
            head_hash=self._tip.head_hash,
            state_root=self._tip.state_root,
        )
        clone._state_root = self._state_root
        clone._state_root_baseline = self._state_root_baseline
        clone._validators = list(self._validators)
        clone._checkpoints = copy.deepcopy(self._checkpoints)
        clone._crash_pending = False
        return clone
