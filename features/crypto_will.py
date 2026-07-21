"""Crypto Will — blockchain inheritance with SQLite persistence (Wave 41)."""

from crypto import native
import json
import threading
import time
from typing import Dict, List, Optional


class CryptoWill:
    def __init__(self, will_id: str, owner: str, heir: str, amount: float,
                 assets: Dict, execution_time: int, witnesses: List[str] = None,
                 created_at: int = None, status: str = "pending"):
        self.will_id = will_id
        self.owner = owner
        self.heir = heir
        self.amount = amount
        self.assets = assets
        self.execution_time = execution_time
        self.created_at = created_at if created_at is not None else int(time.time())
        self.status = status
        self.witnesses = witnesses or []

    @property
    def executed(self) -> bool:
        return self.status == "executed"

    def to_dict(self) -> Dict:
        return {
            "will_id": self.will_id,
            "owner": self.owner[:16] + "..." if len(self.owner) > 20 else self.owner,
            "heir": self.heir[:16] + "..." if len(self.heir) > 20 else self.heir,
            "amount": self.amount,
            "assets": self.assets,
            "execution_time": self.execution_time,
            "created_at": self.created_at,
            "status": self.status,
            "executed": self.executed,
            "witnesses_count": len(self.witnesses),
        }

    def to_db(self) -> Dict:
        return {
            "will_id": self.will_id,
            "owner": self.owner,
            "heir": self.heir,
            "amount": self.amount,
            "assets": self.assets,
            "execution_time": self.execution_time,
            "created_at": self.created_at,
            "status": self.status,
            "witnesses": self.witnesses,
        }


class CryptoWillManager:
    """Manages crypto inheritance — locks L1 ABS on create, transfers on execute."""

    MIN_DELAY = 86400
    MAX_DELAY = 31_536_000

    def __init__(self, blockchain=None, db=None):
        self.wills: Dict[str, CryptoWill] = {}
        self.blockchain = blockchain
        self.db = db
        self._lock = threading.RLock()
        self._load_from_db()
        self._monitor_thread = threading.Thread(
            target=self._check_wills_loop, daemon=True
        )
        self._monitor_thread.start()
        print(f"[CryptoWill] Manager initialized ({len(self.wills)} wills, "
              f"persisted={bool(db)})")

    def _balance(self, addr: str) -> float:
        if self.db and hasattr(self.db, "get_balance"):
            return float(self.db.get_balance(addr))
        if self.blockchain and hasattr(self.blockchain, "get_balance"):
            return float(self.blockchain.get_balance(addr))
        return 0.0

    def _debit(self, addr: str, amount: float) -> bool:
        if amount <= 0 or self._balance(addr) < amount:
            return False
        if self.db and hasattr(self.db, "update_balance"):
            self.db.update_balance(addr, -amount)
            return True
        return False

    def _credit(self, addr: str, amount: float) -> bool:
        if amount <= 0:
            return False
        if self.db and hasattr(self.db, "update_balance"):
            self.db.update_balance(addr, amount)
            return True
        if self.blockchain and hasattr(self.blockchain, "update_balance"):
            self.blockchain.update_balance(addr, amount)
            return True
        return False

    def _load_from_db(self) -> None:
        if not self.db or not hasattr(self.db, "get_crypto_wills"):
            return
        for row in self.db.get_crypto_wills(limit=500):
            if row.get("status") == "cancelled":
                continue
            w = CryptoWill(
                will_id=row["will_id"],
                owner=row["owner"],
                heir=row["heir"],
                amount=row["amount"],
                assets=row.get("assets", {}),
                execution_time=row["execution_time"],
                witnesses=row.get("witnesses", []),
                created_at=row.get("created_at"),
                status=row.get("status", "pending"),
            )
            self.wills[w.will_id] = w

    def _persist(self, will: CryptoWill) -> None:
        if self.db and hasattr(self.db, "save_crypto_will"):
            self.db.save_crypto_will(will.to_db())

    def create_will(self, owner: str, heir: str, amount: float,
                    assets: Dict, execution_delay: int,
                    witnesses: List[str] = None) -> Optional[str]:
        execution_delay = max(self.MIN_DELAY, min(self.MAX_DELAY, execution_delay))
        if not self._debit(owner, amount):
            return None
        will_id = native.sha256_hex(
            f"{owner}{heir}{amount}{time.time()}".encode()
        )[:16]
        execution_time = int(time.time()) + execution_delay
        will = CryptoWill(
            will_id, owner, heir, amount, assets or {},
            execution_time, witnesses or [],
        )
        with self._lock:
            self.wills[will_id] = will
            self._persist(will)
        print(f"[CryptoWill] Created: {will_id} owner={owner[:12]}... "
              f"heir={heir[:12]}... amount={amount} (locked)")
        return will_id

    def get_will(self, will_id: str) -> Optional[Dict]:
        with self._lock:
            w = self.wills.get(will_id)
        return w.to_dict() if w else None

    def get_user_wills(self, address: str) -> List[Dict]:
        with self._lock:
            return [w.to_dict() for w in self.wills.values()
                    if w.owner == address or w.heir == address]

    def list_wills(self, limit: int = 50) -> List[Dict]:
        with self._lock:
            rows = sorted(self.wills.values(), key=lambda w: w.created_at, reverse=True)
            return [w.to_dict() for w in rows[:limit]]

    def cancel_will(self, will_id: str, owner: str) -> bool:
        with self._lock:
            w = self.wills.get(will_id)
            if not w or w.owner != owner or w.status != "pending":
                return False
            if not self._credit(owner, w.amount):
                return False
            w.status = "cancelled"
            del self.wills[will_id]
            if self.db and hasattr(self.db, "save_crypto_will"):
                self.db.save_crypto_will(w.to_db())
            elif self.db and hasattr(self.db, "delete_crypto_will"):
                self.db.delete_crypto_will(will_id)
        print(f"[CryptoWill] Cancelled: {will_id} — refunded {w.amount} ABS")
        return True

    def execute_will(self, will_id: str, force: bool = False) -> bool:
        with self._lock:
            w = self.wills.get(will_id)
            if not w or w.status != "pending":
                return False
            if not force and int(time.time()) < w.execution_time:
                return False
            if not self._credit(w.heir, w.amount):
                return False
        with self._lock:
            w.status = "executed"
            self._persist(w)
            del self.wills[will_id]
        print(f"[CryptoWill] EXECUTED: {will_id} — {w.amount} ABS → {w.heir[:12]}...")
        return True

    def get_stats(self) -> Dict:
        with self._lock:
            total = len(self.wills)
            pending = sum(1 for w in self.wills.values() if w.status == "pending")
            total_amount = sum(w.amount for w in self.wills.values() if w.status == "pending")
        return {
            "total_wills": total,
            "pending_wills": pending,
            "total_locked_amount": total_amount,
            "persisted": bool(self.db),
            "min_delay_sec": self.MIN_DELAY,
        }

    def _check_wills_loop(self):
        while True:
            time.sleep(3600)
            self._execute_due_wills()

    def _execute_due_wills(self):
        now = int(time.time())
        with self._lock:
            due_ids = [
                w.will_id for w in self.wills.values()
                if w.status == "pending" and now >= w.execution_time
            ]
        for wid in due_ids:
            self.execute_will(wid, force=False)
