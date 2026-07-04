#!/usr/bin/env python3
"""Cross-shard 2PC quorum coordinator and resharding planner."""

from __future__ import annotations

import hashlib
import threading
import time
from typing import Callable, Dict, List, Optional, Set


class CrossShardCoordinator:
    """Track shard ACKs for cross-shard transfers and plan resharding epochs."""

    def __init__(self, num_shards: int = 4) -> None:
        self.num_shards = max(1, int(num_shards))
        self._lock = threading.Lock()
        self._acks: Dict[str, Set[int]] = {}
        self._required: Dict[str, Set[int]] = {}
        self._reshard_plan: Optional[dict] = None
        self._migration_queue: List[dict] = []
        self._shard_overrides: Dict[str, int] = {}

    def required_shards(self, from_shard: int, to_shard: int) -> Set[int]:
        return {int(from_shard), int(to_shard)}

    def begin(self, tx_id: str, from_shard: int, to_shard: int) -> None:
        with self._lock:
            self._required[tx_id] = self.required_shards(from_shard, to_shard)
            self._acks.setdefault(tx_id, set())

    def record_ack(self, tx_id: str, shard_id: int) -> bool:
        with self._lock:
            req = self._required.get(tx_id)
            if not req:
                return False
            self._acks.setdefault(tx_id, set()).add(int(shard_id))
            return self._acks[tx_id] >= req

    def quorum_reached(self, tx_id: str) -> bool:
        with self._lock:
            req = self._required.get(tx_id)
            if not req:
                return False
            return self._acks.get(tx_id, set()) >= req

    def clear(self, tx_id: str) -> None:
        with self._lock:
            self._acks.pop(tx_id, None)
            self._required.pop(tx_id, None)

    def plan_reshard(self, new_num_shards: int, effective_epoch: int) -> dict:
        new_num_shards = max(1, int(new_num_shards))
        plan = {
            "from_shards": self.num_shards,
            "to_shards": new_num_shards,
            "effective_epoch": int(effective_epoch),
            "planned_at": time.time(),
            "status": "planned",
        }
        with self._lock:
            self._reshard_plan = plan
            self._migration_queue = []
        return dict(plan)

    def discover_migrations(self, accounts: List[dict], old_shards: int, new_shards: int) -> int:
        """Queue accounts whose shard assignment changes after resharding."""
        added = 0
        with self._lock:
            queued = {r["address"].lower() for r in self._migration_queue}
            for acc in accounts:
                addr = str(acc.get("address", "") or "").strip()
                if not addr:
                    continue
                balance = float(acc.get("balance", 0) or 0)
                if balance <= 0:
                    continue
                old = self.shard_for_address(addr, old_shards)
                new = self.shard_for_address(addr, new_shards)
                if old == new or addr.lower() in queued:
                    continue
                self._migration_queue.append({
                    "address": addr,
                    "from_shard": old,
                    "to_shard": new,
                    "balance": balance,
                    "queued_at": time.time(),
                    "status": "pending",
                })
                queued.add(addr.lower())
                added += 1
        return added

    def queue_address_migration(self, address: str, from_shard: int, to_shard: int) -> dict:
        row = {
            "address": address,
            "from_shard": int(from_shard),
            "to_shard": int(to_shard),
            "queued_at": time.time(),
            "status": "pending",
        }
        with self._lock:
            self._migration_queue.append(row)
        return row

    def apply_reshard(self) -> bool:
        with self._lock:
            if not self._reshard_plan or self._reshard_plan.get("status") != "planned":
                return False
            self.num_shards = int(self._reshard_plan["to_shards"])
            self._reshard_plan["status"] = "active"
            self._reshard_plan["applied_at"] = time.time()
            for row in self._migration_queue:
                if row.get("status") == "done":
                    addr = str(row.get("address", "")).lower()
                    if addr:
                        self._shard_overrides[addr] = int(row["to_shard"])
            return True

    def resolve_shard(self, address: str, default_shard: int) -> int:
        key = (address or "").lower()
        with self._lock:
            if key in self._shard_overrides:
                return int(self._shard_overrides[key])
        return int(default_shard)

    def pending_migrations(self) -> List[dict]:
        with self._lock:
            return [dict(row) for row in self._migration_queue if row.get("status") == "pending"]

    def export_migration_debit(self, row: dict, db, owns_shard: Callable[[int], bool]) -> Optional[dict]:
        """Debit balance on source shard; return gossip payload for destination."""
        from_shard = int(row.get("from_shard", -1))
        if not owns_shard(from_shard):
            return None
        addr = row.get("address", "")
        if not addr or not db or not hasattr(db, "get_balance"):
            return None
        balance = float(db.get_balance(addr))
        if balance <= 0:
            self.complete_migration(addr)
            return {"address": addr, "status": "zero_balance"}
        if hasattr(db, "update_balance"):
            db.update_balance(addr, -balance)
        row["balance"] = balance
        row["status"] = "debited"
        return {
            "type": "shard_migration",
            "address": addr,
            "from_shard": from_shard,
            "to_shard": int(row.get("to_shard", 0)),
            "balance": balance,
        }

    def apply_migration_credit(self, payload: dict, db, owns_shard: Callable[[int], bool]) -> bool:
        if not isinstance(payload, dict) or payload.get("type") != "shard_migration":
            return False
        to_shard = int(payload.get("to_shard", -1))
        if not owns_shard(to_shard):
            return False
        addr = payload.get("address", "")
        balance = float(payload.get("balance", 0) or 0)
        if not addr or balance <= 0 or not db or not hasattr(db, "update_balance"):
            return False
        db.update_balance(addr, balance)
        self.complete_migration(addr)
        return True

    def process_local_migrations(
        self,
        db,
        owns_shard: Callable[[int], bool],
        limit: int = 20,
    ) -> dict:
        """Process pending migrations on this node (routing or distributed)."""
        processed = 0
        debited = 0
        completed = 0
        payloads: List[dict] = []
        for row in self.pending_migrations()[: max(1, int(limit))]:
            processed += 1
            from_shard = int(row.get("from_shard", -1))
            to_shard = int(row.get("to_shard", -1))
            if owns_shard(from_shard) and owns_shard(to_shard):
                addr = row.get("address", "")
                if addr and db and hasattr(db, "get_balance"):
                    balance = float(db.get_balance(addr))
                    if balance > 0 and hasattr(db, "update_balance"):
                        pass
                self.complete_migration(addr)
                completed += 1
                continue
            payload = self.export_migration_debit(row, db, owns_shard)
            if payload:
                if payload.get("status") == "zero_balance":
                    completed += 1
                else:
                    debited += 1
                    payloads.append(payload)
        return {
            "processed": processed,
            "debited": debited,
            "completed": completed,
            "payloads": payloads,
        }

    def complete_migration(self, address: str) -> bool:
        with self._lock:
            for row in self._migration_queue:
                if row.get("address", "").lower() == address.lower() and row.get("status") in (
                    "pending",
                    "debited",
                ):
                    row["status"] = "done"
                    row["completed_at"] = time.time()
                    self._shard_overrides[address.lower()] = int(row.get("to_shard", 0))
                    return True
        return False

    def shard_for_address(self, address: str, num_shards: Optional[int] = None) -> int:
        n = max(1, int(num_shards or self.num_shards))
        digest = hashlib.sha256((address or "").encode()).hexdigest()
        return int(digest, 16) % n

    def status(self) -> dict:
        with self._lock:
            return {
                "num_shards": self.num_shards,
                "pending_quorums": len(self._required),
                "reshard_plan": dict(self._reshard_plan) if self._reshard_plan else None,
                "pending_migrations": len([r for r in self._migration_queue if r.get("status") == "pending"]),
                "shard_overrides": len(self._shard_overrides),
            }

    def migrations_view(self) -> List[dict]:
        with self._lock:
            return [dict(row) for row in self._migration_queue]
