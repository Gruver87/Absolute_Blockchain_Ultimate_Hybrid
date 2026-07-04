#!/usr/bin/env python3
"""Cross-shard 2PC quorum coordinator and resharding planner."""

from __future__ import annotations

import hashlib
import threading
import time
from typing import Dict, List, Optional, Set


class CrossShardCoordinator:
    """Track shard ACKs for cross-shard transfers and plan resharding epochs."""

    def __init__(self, num_shards: int = 4) -> None:
        self.num_shards = max(1, int(num_shards))
        self._lock = threading.Lock()
        self._acks: Dict[str, Set[int]] = {}
        self._required: Dict[str, Set[int]] = {}
        self._reshard_plan: Optional[dict] = None
        self._migration_queue: List[dict] = []

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
            return True

    def pending_migrations(self) -> List[dict]:
        with self._lock:
            return [dict(row) for row in self._migration_queue if row.get("status") == "pending"]

    def complete_migration(self, address: str) -> bool:
        with self._lock:
            for row in self._migration_queue:
                if row.get("address", "").lower() == address.lower() and row.get("status") == "pending":
                    row["status"] = "done"
                    row["completed_at"] = time.time()
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
            }
