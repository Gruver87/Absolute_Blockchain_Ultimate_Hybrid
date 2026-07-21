#!/usr/bin/env python3
"""Cross-shard 2PC quorum coordinator and resharding planner."""

from __future__ import annotations

import logging
import math
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set

from crypto import native

logger = logging.getLogger(__name__)

class CrossShardCoordinator:
    """Track shard ACKs for cross-shard transfers and plan resharding epochs."""

    def __init__(self, num_shards: int = 4, validator_quorum: float = 2 / 3) -> None:
        self.num_shards = max(1, int(num_shards))
        self.validator_quorum = max(0.5, min(1.0, float(validator_quorum)))
        self._lock = threading.Lock()
        self._acks: Dict[str, Set[int]] = {}
        self._required: Dict[str, Set[int]] = {}
        self._validator_acks: Dict[str, Dict[int, Set[str]]] = {}
        self._shard_validators: Dict[int, Set[str]] = {}
        self._reshard_plan: Optional[dict] = None
        self._migration_queue: List[dict] = []
        self._shard_overrides: Dict[str, int] = {}

    def quorum_size(self, committee_size: int) -> int:
        n = max(0, int(committee_size))
        if n <= 0:
            return 0
        return max(1, math.ceil(n * self.validator_quorum))

    def register_shard_validator(self, shard_id: int, validator_id: str) -> None:
        vid = (validator_id or "").strip()
        if not vid:
            return
        with self._lock:
            self._shard_validators.setdefault(int(shard_id), set()).add(vid)

    def load_shard_committees(self, committees: Dict[int, List[str]]) -> int:
        """Bulk load {shard_id: [validator_id, ...]}. Returns validator count."""
        added = 0
        with self._lock:
            for shard_id, members in (committees or {}).items():
                bucket = self._shard_validators.setdefault(int(shard_id), set())
                for member in members or []:
                    vid = str(member or "").strip()
                    if vid and vid not in bucket:
                        bucket.add(vid)
                        added += 1
        return added

    def load_validators_from_manifest(self, manifest: dict, num_shards: Optional[int] = None) -> int:
        """Assign manifest validators to shards (explicit shard_id or hash of node_id)."""
        n = max(1, int(num_shards or self.num_shards))
        committees: Dict[int, List[str]] = {}
        for row in manifest.get("validators") or []:
            if not isinstance(row, dict):
                continue
            vid = str(row.get("node_id") or row.get("address") or "").strip()
            if not vid:
                continue
            if row.get("shard_id") is not None:
                shard = int(row["shard_id"]) % n
            else:
                digest = native.hash_text(vid)
                shard = int(digest, 16) % n
            committees.setdefault(shard, []).append(vid)
        return self.load_shard_committees(committees)

    def shard_committee(self, shard_id: int) -> Set[str]:
        with self._lock:
            return set(self._shard_validators.get(int(shard_id), set()))

    def has_shard_committee(self, shard_id: int) -> bool:
        return bool(self.shard_committee(shard_id))

    def required_shards(self, from_shard: int, to_shard: int) -> Set[int]:
        return {int(from_shard), int(to_shard)}

    def begin(self, tx_id: str, from_shard: int, to_shard: int) -> None:
        with self._lock:
            self._required[tx_id] = self.required_shards(from_shard, to_shard)
            self._acks.setdefault(tx_id, set())
            self._validator_acks.pop(tx_id, None)

    def _validator_shard_quorum_met_unlocked(self, tx_id: str, shard_id: int) -> bool:
        committee = self._shard_validators.get(int(shard_id), set())
        if not committee:
            return int(shard_id) in self._acks.get(tx_id, set())
        acks = self._validator_acks.get(tx_id, {}).get(int(shard_id), set())
        return len(acks) >= self.quorum_size(len(committee))

    def _quorum_reached_unlocked(self, tx_id: str) -> bool:
        req = self._required.get(tx_id)
        if not req:
            return False
        for sid in req:
            if not self._validator_shard_quorum_met_unlocked(tx_id, sid):
                return False
        return True

    def record_validator_ack(self, tx_id: str, shard_id: int, validator_id: str) -> bool:
        vid = (validator_id or "").strip()
        if not vid:
            return False
        with self._lock:
            req = self._required.get(tx_id)
            if not req or int(shard_id) not in req:
                return False
            committee = self._shard_validators.get(int(shard_id), set())
            if committee and vid not in committee:
                return False
            per_shard = self._validator_acks.setdefault(tx_id, {}).setdefault(int(shard_id), set())
            per_shard.add(vid)
            if self._validator_shard_quorum_met_unlocked(tx_id, int(shard_id)):
                self._acks.setdefault(tx_id, set()).add(int(shard_id))
            return self._quorum_reached_unlocked(tx_id)

    def record_ack(self, tx_id: str, shard_id: int) -> bool:
        with self._lock:
            req = self._required.get(tx_id)
            if not req:
                return False
            sid = int(shard_id)
            if self._shard_validators.get(sid):
                return False
            self._acks.setdefault(tx_id, set()).add(sid)
            return self._quorum_reached_unlocked(tx_id)

    def quorum_reached(self, tx_id: str) -> bool:
        with self._lock:
            return self._quorum_reached_unlocked(tx_id)

    def quorum_status(self, tx_id: str) -> dict:
        with self._lock:
            req = set(self._required.get(tx_id, set()))
            shards = []
            for sid in sorted(req):
                committee = sorted(self._shard_validators.get(sid, set()))
                acks = sorted(self._validator_acks.get(tx_id, {}).get(sid, set()))
                need = self.quorum_size(len(committee)) if committee else 1
                shards.append({
                    "shard_id": sid,
                    "committee_size": len(committee),
                    "acks": len(acks),
                    "required_acks": need,
                    "validator_acks": acks,
                    "committee": committee,
                    "met": self._validator_shard_quorum_met_unlocked(tx_id, sid),
                })
            return {
                "tx_id": tx_id,
                "required_shards": sorted(req),
                "quorum_reached": self._quorum_reached_unlocked(tx_id) if req else False,
                "validator_quorum": self.validator_quorum,
                "shards": shards,
            }

    def clear(self, tx_id: str) -> None:
        with self._lock:
            self._acks.pop(tx_id, None)
            self._required.pop(tx_id, None)
            self._validator_acks.pop(tx_id, None)

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
                logger.info(
                    "cross-shard migration same-node noop address=%s from=%s to=%s",
                    addr,
                    from_shard,
                    to_shard,
                )
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
        digest = native.hash_text(address or "")
        return int(digest, 16) % n

    def status(self) -> dict:
        with self._lock:
            committees = {
                str(sid): len(members)
                for sid, members in self._shard_validators.items()
            }
            return {
                "num_shards": self.num_shards,
                "validator_quorum": self.validator_quorum,
                "shard_committees": committees,
                "pending_quorums": len(self._required),
                "reshard_plan": dict(self._reshard_plan) if self._reshard_plan else None,
                "pending_migrations": len([r for r in self._migration_queue if r.get("status") == "pending"]),
                "shard_overrides": len(self._shard_overrides),
            }

    def migrations_view(self) -> List[dict]:
        with self._lock:
            return [dict(row) for row in self._migration_queue]
