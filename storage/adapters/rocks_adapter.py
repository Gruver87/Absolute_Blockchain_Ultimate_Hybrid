"""RocksDB storage adapter (ADR 0006 Step B).

Implements ``StoragePort`` over ``RocksChainStore`` / Hybrid-like façades.
Domain never sees CF names, keycodec, or ``RocksWriteBatch`` — those stay here.

Atomic tip advance:
- Prefer one ``store.atomic()`` WriteBatch: block body + indexes + account
  writeback (+ tip meta already written by ``_insert_block``).
- Fallback: ``persist_block_atomic`` then ``commit_writeback_bundle``.
- ``sync_writes`` / WAL durability remain engine-owned (store open flags).

Crash recovery:
- On open, tip must resolve to an existing body; otherwise rewind to the last
  consistent height or fail-closed ``StorageCorruptionError``.
"""

from __future__ import annotations

import errno
import logging
from contextlib import AbstractContextManager
from typing import Any, Dict, List, Mapping, Optional, Sequence

from storage.types import (
    AccountRecord,
    BlockRecord,
    StorageConflictError,
    StorageCorruptionError,
    StorageError,
    StorageFullError,
    StorageUnavailableError,
    TipMeta,
)

logger = logging.getLogger("Storage.RocksAdapter")

__all__ = ["RocksDBStorageAdapter", "map_engine_error"]


def map_engine_error(exc: BaseException) -> StorageError:
    """Map OS / Rocks / decode failures to typed storage errors."""
    msg = str(exc or type(exc).__name__)
    low = msg.lower()
    en = getattr(exc, "errno", None)
    if (
        en == errno.ENOSPC
        or getattr(exc, "winerror", None) == 112  # ERROR_DISK_FULL
        or "no space" in low
        or "enospc" in low
        or "disk full" in low
        or "not enough space" in low
    ):
        return StorageFullError(msg, reason_code="disk_full")
    if (
        "corrupt" in low
        or "checksum" in low
        or "corruption" in low
        or ("json" in low and ("decode" in low or "expect" in low or "parse" in low))
        or "utf-8" in low
        or "invalid utf" in low
        or "truncated" in low
    ):
        return StorageCorruptionError(msg, reason_code="corruption")
    return StorageUnavailableError(msg, reason_code="unavailable")


# Back-compat alias used by unit tests.
_map_engine_error = map_engine_error


def _coerce_block(block: BlockRecord | Mapping[str, Any]) -> BlockRecord:
    if isinstance(block, BlockRecord):
        return block
    return BlockRecord.from_mapping(block)


def _normalize_accounts(
    accounts: Sequence[AccountRecord] | Mapping[str, Mapping[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    if isinstance(accounts, Mapping):
        for addr, row in accounts.items():
            if isinstance(row, AccountRecord):
                rec = row
            else:
                rec = AccountRecord.from_mapping(str(addr), row)
            if not rec.address:
                continue
            out[rec.address] = dict(rec.to_mapping())
        return out
    for row in accounts or ():
        if isinstance(row, AccountRecord):
            rec = row
        elif isinstance(row, Mapping):
            rec = AccountRecord.from_mapping(str(row.get("address") or ""), row)
        else:
            continue
        if not rec.address:
            continue
        out[rec.address] = dict(rec.to_mapping())
    return out


def _block_burn_fields(blk: BlockRecord) -> tuple[float, str]:
    payload = blk.payload or {}
    try:
        burned = float(payload.get("total_burned") or payload.get("burned_amount") or 0.0)
    except (TypeError, ValueError):
        burned = 0.0
    burn_addr = str(payload.get("burn_address") or "")
    return burned, burn_addr


class _RocksUoW:
    """Staged unit of work; durable only after successful ``commit()``."""

    def __init__(
        self,
        adapter: "RocksDBStorageAdapter",
        *,
        expected_parent: str,
        expected_tip_height: int,
    ) -> None:
        self._adapter = adapter
        self._expected_parent = str(expected_parent or "")
        self._expected_tip_height = int(expected_tip_height)
        self._block: Optional[BlockRecord] = None
        self._txs: List[Dict[str, Any]] = []
        self._accounts: Dict[str, Dict[str, Any]] = {}
        self._tip: Optional[TipMeta] = None
        self._aborted = False
        self._committed = False

    def write_block(self, block: BlockRecord | Mapping[str, Any]) -> None:
        self._ensure_open()
        self._block = _coerce_block(block)

    def write_transactions(self, transactions: Sequence[Mapping[str, Any]]) -> None:
        self._ensure_open()
        self._txs = [dict(t) for t in (transactions or ()) if isinstance(t, Mapping)]

    def write_state_delta(
        self,
        accounts: Sequence[AccountRecord] | Mapping[str, Mapping[str, Any]],
    ) -> None:
        self._ensure_open()
        self._accounts.update(_normalize_accounts(accounts))

    def set_tip(self, tip: TipMeta) -> None:
        self._ensure_open()
        if not isinstance(tip, TipMeta):
            raise StorageUnavailableError(
                "set_tip requires TipMeta", reason_code="invalid_tip"
            )
        self._tip = tip

    def commit(self) -> None:
        self._ensure_open()
        adapter = self._adapter
        store = adapter._store

        tip_h, tip_hash = adapter._read_tip_snapshot()

        if self._expected_tip_height >= 0 and tip_h != self._expected_tip_height:
            raise StorageConflictError(
                f"stale tip height want={self._expected_tip_height} got={tip_h}",
                reason_code="stale_tip_height",
            )
        if self._expected_parent and tip_h > 0:
            if tip_hash.lower() != self._expected_parent.lower():
                raise StorageConflictError(
                    "expected_parent mismatch",
                    reason_code="expected_parent_mismatch",
                )

        if self._block is None:
            raise StorageUnavailableError("no block staged", reason_code="empty_uow")

        blk = self._block
        hh = str(blk.block_hash or "")
        # Idempotent retry (import / crash-after-ack culture).
        try:
            if hh and store.get_block_by_hash(hh) is not None:
                self._committed = True
                adapter._last_flush_ok = True
                return
        except Exception as exc:
            raise map_engine_error(exc) from exc

        blk_map = dict(blk.to_mapping())
        if self._tip is not None:
            # Keep payload tip fields coherent with TipMeta fence.
            if self._tip.head_hash:
                blk_map["hash"] = str(self._tip.head_hash)
                blk_map["block_hash"] = str(self._tip.head_hash)
            if self._tip.state_root:
                blk_map["state_root"] = str(self._tip.state_root)
            blk_map["height"] = int(self._tip.height or blk.height)

        burned, burn_addr = _block_burn_fields(blk)
        txs = list(self._txs)
        accounts = dict(self._accounts)

        try:
            adapter._commit_block_bundle(
                block=blk_map,
                transactions=txs,
                accounts=accounts,
                burned_amount=burned,
                burn_address=burn_addr,
                tip=self._tip,
            )
            adapter._last_flush_ok = True
            self._committed = True
        except StorageError:
            adapter._last_flush_ok = False
            raise
        except Exception as exc:
            adapter._last_flush_ok = False
            raise map_engine_error(exc) from exc

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
            raise StorageUnavailableError(
                "uow already committed", reason_code="committed"
            )


class RocksDBStorageAdapter:
    """``StoragePort`` implementation over RocksChainStore / HybridDatabase-like store."""

    def __init__(
        self,
        store: Any,
        *,
        fail_closed_repair: bool = True,
        repair_on_open: bool = True,
    ) -> None:
        if store is None:
            raise StorageUnavailableError(
                "store is required", reason_code="missing_store"
            )
        self._store = store
        self._fail_closed_repair = bool(fail_closed_repair)
        self._last_flush_ok = True
        if repair_on_open:
            self.repair_tip_consistency()

    # ── StoragePort composite ────────────────────────────────────────────────

    @property
    def blocks(self) -> "RocksDBStorageAdapter":
        return self

    @property
    def state(self) -> "RocksDBStorageAdapter":
        return self

    @property
    def meta(self) -> "RocksDBStorageAdapter":
        return self

    @property
    def health(self) -> "RocksDBStorageAdapter":
        return self

    def begin_block_commit(
        self,
        *,
        expected_parent: str = "",
        expected_tip_height: int = -1,
    ) -> _RocksUoW:
        return _RocksUoW(
            self,
            expected_parent=expected_parent,
            expected_tip_height=expected_tip_height,
        )

    # ── Internal tip / commit helpers ────────────────────────────────────────

    def _read_tip_snapshot(self) -> tuple[int, str]:
        store = self._store
        try:
            tip_h = int(store.get_chain_tip() or 0)
        except Exception as exc:
            raise map_engine_error(exc) from exc
        tip_hash = ""
        try:
            last = store.get_last_block()
            if isinstance(last, Mapping):
                tip_hash = str(last.get("hash") or last.get("block_hash") or "")
        except Exception as exc:
            raise map_engine_error(exc) from exc
        return tip_h, tip_hash

    def _commit_block_bundle(
        self,
        *,
        block: Dict[str, Any],
        transactions: List[Dict[str, Any]],
        accounts: Dict[str, Dict[str, Any]],
        burned_amount: float,
        burn_address: str,
        tip: Optional[TipMeta],
    ) -> None:
        """Persist block (+ optional accounts) with best-effort single-batch atomicity."""
        store = self._store
        height = int(block.get("height") or 0)

        # Preferred path: one Rocks WriteBatch via store.atomic() + locked helpers.
        if hasattr(store, "atomic") and hasattr(store, "_persist_block_locked"):
            cm = store.atomic()
            if isinstance(cm, AbstractContextManager) or hasattr(cm, "__enter__"):
                with cm:
                    store._persist_block_locked(
                        dict(block),
                        list(transactions),
                        float(burned_amount or 0.0),
                        str(burn_address or ""),
                    )
                    if accounts:
                        self._writeback_accounts(
                            accounts,
                            block_height=height,
                            inside_atomic=True,
                        )
                    self._apply_tip_meta(tip, block)
                return

        # Fallback: public persist_block_atomic then writeback (two store commits).
        ok = False
        try:
            ok = bool(
                store.persist_block_atomic(
                    dict(block),
                    list(transactions),
                    burned_amount=float(burned_amount or 0.0),
                    burn_address=str(burn_address or ""),
                )
            )
        except Exception as exc:
            raise map_engine_error(exc) from exc
        if not ok:
            raise StorageUnavailableError(
                "persist_block_atomic returned False",
                reason_code="persist_failed",
            )
        if accounts:
            self._writeback_accounts(
                accounts,
                block_height=height,
                inside_atomic=False,
            )
        self._apply_tip_meta(tip, block)

    def _writeback_accounts(
        self,
        accounts: Dict[str, Dict[str, Any]],
        *,
        block_height: int,
        inside_atomic: bool,
    ) -> None:
        store = self._store
        if hasattr(store, "commit_writeback_bundle"):
            store.commit_writeback_bundle(
                dict(accounts),
                None,
                block_height=int(block_height),
                tx_hash="",
                timestamp=0,
            )
            return
        if hasattr(store, "commit_writeback_accounts"):
            store.commit_writeback_accounts(dict(accounts))
            return
        if inside_atomic and hasattr(store, "_save_account_row"):
            for addr, row in accounts.items():
                payload = dict(row)
                payload["address"] = str(addr)
                store._save_account_row(payload)
            return
        raise StorageUnavailableError(
            "store has no writeback path",
            reason_code="no_writeback",
        )

    def _apply_tip_meta(self, tip: Optional[TipMeta], block: Mapping[str, Any]) -> None:
        """Optional explicit tip meta; ``_insert_block`` already fences tip on Rocks."""
        store = self._store
        if tip is None:
            return
        hh = str(tip.head_hash or block.get("hash") or block.get("block_hash") or "")
        height = int(tip.height)
        if hasattr(store, "set_chain_tip_meta"):
            store.set_chain_tip_meta(height, hh)
            return
        if hasattr(store, "set_meta"):
            store.set_meta("chain_tip", height)
            if hh:
                # chain_tip_hash is stored as raw bytes in RocksChainStore._insert_block;
                # set_meta JSON-encodes — only write height via set_meta for parity.
                pass
            if tip.state_root and hasattr(store, "set_meta"):
                store.set_meta("live_state_root", str(tip.state_root))
                store.set_meta("live_state_root_height", height)

    # ── BlockStorePort ───────────────────────────────────────────────────────

    def tip_height(self) -> int:
        try:
            return int(self._store.get_chain_tip() or 0)
        except Exception as exc:
            raise map_engine_error(exc) from exc

    def tip_hash(self) -> str:
        try:
            last = self._store.get_last_block()
            if isinstance(last, Mapping):
                return str(last.get("hash") or last.get("block_hash") or "")
            return ""
        except Exception as exc:
            raise map_engine_error(exc) from exc

    def has_hash(self, block_hash: str) -> bool:
        key = str(block_hash or "").strip()
        if not key:
            return False
        try:
            return self._store.get_block_by_hash(key) is not None
        except Exception as exc:
            raise map_engine_error(exc) from exc

    def get_by_height(self, height: int) -> Optional[BlockRecord]:
        try:
            raw = self._store.get_block(int(height))
        except Exception as exc:
            raise map_engine_error(exc) from exc
        if raw is None:
            return None
        if not isinstance(raw, Mapping):
            raise StorageCorruptionError(
                f"non-mapping block at height={height}",
                reason_code="corrupt_block",
            )
        return BlockRecord.from_mapping(raw)

    def get_by_hash(self, block_hash: str) -> Optional[BlockRecord]:
        key = str(block_hash or "").strip()
        if not key:
            return None
        try:
            raw = self._store.get_block_by_hash(key)
        except Exception as exc:
            raise map_engine_error(exc) from exc
        if raw is None:
            return None
        if not isinstance(raw, Mapping):
            raise StorageCorruptionError(
                f"non-mapping block hash={key[:16]}",
                reason_code="corrupt_block",
            )
        return BlockRecord.from_mapping(raw)

    def iterate_heights(self, from_height: int, to_height: int) -> Sequence[BlockRecord]:
        lo = int(from_height)
        hi = int(to_height)
        if hi < lo:
            return []
        out: List[BlockRecord] = []
        for h in range(lo, hi + 1):
            blk = self.get_by_height(h)
            if blk is not None:
                out.append(blk)
        return out

    def reorg_truncate_above(self, height: int) -> None:
        try:
            self._store.reorg_truncate_above(int(height))
        except Exception as exc:
            raise map_engine_error(exc) from exc

    # ── StateStorePort ───────────────────────────────────────────────────────

    def get_account(self, address: str) -> Optional[AccountRecord]:
        addr = str(address or "").strip()
        if not addr:
            return None
        try:
            raw = self._store.get_account(addr)
        except Exception as exc:
            raise map_engine_error(exc) from exc
        if raw is None:
            return None
        if not isinstance(raw, Mapping):
            raise StorageCorruptionError(
                "corrupt account row",
                reason_code="corrupt_account",
            )
        return AccountRecord.from_mapping(addr, raw)

    def get_state_root(self) -> str:
        store = self._store
        if hasattr(store, "get_live_state_root_meta"):
            try:
                root, _h = store.get_live_state_root_meta()
                return str(root or "")
            except Exception as exc:
                raise map_engine_error(exc) from exc
        if hasattr(store, "get_state_root"):
            try:
                return str(store.get_state_root() or "")
            except Exception as exc:
                raise map_engine_error(exc) from exc
        if hasattr(store, "get_meta"):
            try:
                return str(store.get_meta("live_state_root") or "")
            except Exception as exc:
                raise map_engine_error(exc) from exc
        return ""

    def get_state_root_baseline(self) -> int:
        store = self._store
        if hasattr(store, "get_state_root_baseline"):
            try:
                return int(store.get_state_root_baseline() or 0)
            except Exception as exc:
                raise map_engine_error(exc) from exc
        if hasattr(store, "get_meta"):
            try:
                return int(store.get_meta("state_root_baseline") or 0)
            except Exception as exc:
                raise map_engine_error(exc) from exc
        return 0

    # ── MetaStorePort ────────────────────────────────────────────────────────

    def get_validators(self) -> Sequence[Mapping[str, Any]]:
        store = self._store
        if not hasattr(store, "get_validators"):
            return []
        try:
            rows = store.get_validators()
            return [dict(r) for r in (rows or []) if isinstance(r, Mapping)]
        except Exception as exc:
            raise map_engine_error(exc) from exc

    def get_checkpoint(self, epoch: int) -> Optional[Mapping[str, Any]]:
        store = self._store
        if hasattr(store, "get_checkpoint"):
            try:
                row = store.get_checkpoint(int(epoch))
                return dict(row) if isinstance(row, Mapping) else None
            except Exception as exc:
                raise map_engine_error(exc) from exc
        if hasattr(store, "get_meta"):
            try:
                row = store.get_meta(f"checkpoint:{int(epoch)}")
                return dict(row) if isinstance(row, Mapping) else None
            except Exception as exc:
                raise map_engine_error(exc) from exc
        return None

    def put_checkpoint(self, epoch: int, data: Mapping[str, Any]) -> None:
        store = self._store
        payload = dict(data or {})
        if hasattr(store, "put_checkpoint"):
            try:
                store.put_checkpoint(int(epoch), payload)
                return
            except Exception as exc:
                raise map_engine_error(exc) from exc
        if hasattr(store, "set_meta"):
            try:
                store.set_meta(f"checkpoint:{int(epoch)}", payload)
                return
            except Exception as exc:
                raise map_engine_error(exc) from exc
        raise StorageUnavailableError(
            "store has no checkpoint path",
            reason_code="no_checkpoint",
        )

    # ── StorageHealthPort ────────────────────────────────────────────────────

    def ping(self) -> bool:
        try:
            _ = self.tip_height()
            return True
        except Exception:
            return False

    def approximate_size(self) -> int:
        store = self._store
        if hasattr(store, "approximate_size"):
            try:
                return int(store.approximate_size() or 0)
            except Exception:
                return 0
        return 0

    def last_flush_ok(self) -> bool:
        return bool(self._last_flush_ok)

    # ── Repair ───────────────────────────────────────────────────────────────

    def repair_tip_consistency(self) -> None:
        """Ensure tip points at an existing body; rewind or fail-closed."""
        store = self._store
        try:
            tip_h = int(store.get_chain_tip() or 0)
        except Exception as exc:
            raise map_engine_error(exc) from exc
        if tip_h <= 0:
            return

        consistent = int(tip_h)
        while consistent > 0:
            try:
                body = store.get_block(consistent)
            except Exception as exc:
                mapped = map_engine_error(exc)
                if isinstance(mapped, StorageCorruptionError) and self._fail_closed_repair:
                    raise mapped from exc
                body = None
            if body is not None:
                break
            consistent -= 1

        if consistent == tip_h:
            return

        logger.warning(
            "[RocksAdapter] tip #%s missing body — repair rewind to #%s",
            tip_h,
            consistent,
        )
        try:
            store.reorg_truncate_above(int(consistent))
        except Exception as exc:
            raise map_engine_error(exc) from exc

        # Verify repair landed on a body (or empty chain).
        if consistent <= 0:
            return
        try:
            body = store.get_block(consistent)
        except Exception as exc:
            raise map_engine_error(exc) from exc
        if body is None and self._fail_closed_repair:
            raise StorageCorruptionError(
                f"tip #{tip_h} orphan after crash; repair to #{consistent} failed",
                reason_code="tip_orphan",
            )
