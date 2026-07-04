#!/usr/bin/env python3
"""In-memory eth_newFilter / eth_getFilterChanges store (HTTP JSON-RPC polling)."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, List, Optional

FILTER_TTL_SEC = 300


class EthFilterStore:
    """Thread-safe filter registry for Ethereum-compatible polling filters."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._next_id = 1
        self._filters: Dict[int, Dict[str, Any]] = {}

    def _touch(self, fid: int) -> None:
        if fid in self._filters:
            self._filters[fid]["last_access"] = time.time()

    def _prune_expired(self, now: float) -> None:
        expired = [
            fid
            for fid, row in self._filters.items()
            if now - float(row.get("last_access", now)) > FILTER_TTL_SEC
        ]
        for fid in expired:
            del self._filters[fid]

    @staticmethod
    def _parse_id(raw) -> Optional[int]:
        try:
            return int(raw, 16) if str(raw).startswith("0x") else int(raw)
        except (TypeError, ValueError):
            return None

    def new_log_filter(self, filt: Dict[str, Any], bc) -> str:
        now = time.time()
        tip = int(bc.get_height()) if bc else 0
        with self._lock:
            self._prune_expired(now)
            fid = self._next_id
            self._next_id += 1
            self._filters[fid] = {
                "kind": "logs",
                "filter": dict(filt or {}),
                "last_height": tip,
                "created_at": now,
                "last_access": now,
            }
        return hex(fid)

    def new_block_filter(self, bc) -> str:
        now = time.time()
        tip = int(bc.get_height()) if bc else 0
        with self._lock:
            self._prune_expired(now)
            fid = self._next_id
            self._next_id += 1
            self._filters[fid] = {
                "kind": "block",
                "last_height": tip,
                "created_at": now,
                "last_access": now,
            }
        return hex(fid)

    def new_pending_filter(self, mempool) -> str:
        now = time.time()
        seen = self._pending_hashes(mempool)
        with self._lock:
            self._prune_expired(now)
            fid = self._next_id
            self._next_id += 1
            self._filters[fid] = {
                "kind": "pending",
                "seen": seen,
                "created_at": now,
                "last_access": now,
            }
        return hex(fid)

    @staticmethod
    def _pending_hashes(mempool) -> set:
        if not mempool:
            return set()
        if hasattr(mempool, "get_sorted_transactions"):
            rows = mempool.get_sorted_transactions()
            return {str(r.get("hash", "")) for r in rows if r.get("hash")}
        return set()

    def uninstall(self, filter_id) -> bool:
        fid = self._parse_id(filter_id)
        if fid is None:
            return False
        with self._lock:
            if fid in self._filters:
                del self._filters[fid]
                return True
        return False

    def get_filter_logs(
        self,
        filter_id,
        bc,
        query_logs: Callable[[Dict[str, Any], Any], List[Dict]],
    ) -> List[Dict]:
        fid = self._parse_id(filter_id)
        if fid is None:
            return []
        with self._lock:
            row = self._filters.get(fid)
            if not row or row.get("kind") != "logs":
                return []
            self._touch(fid)
            filt = dict(row.get("filter") or {})
        filt.setdefault("toBlock", "latest")
        return query_logs(filt, bc)

    def get_filter_changes(
        self,
        filter_id,
        bc,
        mempool,
        query_logs: Callable[[Dict[str, Any], Any], List[Dict]],
    ) -> List[Any]:
        fid = self._parse_id(filter_id)
        if fid is None:
            return []
        with self._lock:
            row = self._filters.get(fid)
            if not row:
                return []
            self._touch(fid)
            kind = row.get("kind")

        if kind == "logs":
            return self._log_changes(fid, row, bc, query_logs)
        if kind == "block":
            return self._block_changes(fid, row, bc)
        if kind == "pending":
            return self._pending_changes(fid, row, mempool)
        return []

    def _log_changes(
        self,
        fid: int,
        row: Dict[str, Any],
        bc,
        query_logs: Callable[[Dict[str, Any], Any], List[Dict]],
    ) -> List[Dict]:
        tip = int(bc.get_height()) if bc else 0
        last = int(row.get("last_height", tip))
        if tip <= last:
            return []
        filt = dict(row.get("filter") or {})
        filt["fromBlock"] = hex(last + 1)
        filt["toBlock"] = hex(tip)
        logs = query_logs(filt, bc)
        with self._lock:
            if fid in self._filters:
                self._filters[fid]["last_height"] = tip
        return logs

    def _block_changes(self, fid: int, row: Dict[str, Any], bc) -> List[str]:
        if not bc:
            return []
        tip = int(bc.get_height())
        last = int(row.get("last_height", tip))
        if tip <= last:
            return []
        out: List[str] = []
        for height in range(last + 1, tip + 1):
            blk = bc.get_block(height)
            if not blk:
                continue
            block_hash = blk.get("hash", blk.get("block_hash", ""))
            if block_hash:
                out.append(block_hash if str(block_hash).startswith("0x") else "0x" + str(block_hash))
        with self._lock:
            if fid in self._filters:
                self._filters[fid]["last_height"] = tip
        return out

    def _pending_changes(self, fid: int, row: Dict[str, Any], mempool) -> List[str]:
        current = self._pending_hashes(mempool)
        seen = set(row.get("seen") or set())
        new_hashes = [h for h in sorted(current) if h not in seen]
        with self._lock:
            if fid in self._filters:
                self._filters[fid]["seen"] = seen | set(new_hashes)
        return new_hashes
