"""Crypto Will — blockchain-based inheritance and testament system."""

import hashlib
import json
import threading
import time
from typing import Dict, List, Optional


class CryptoWill:
    def __init__(self, will_id: str, owner: str, heir: str, amount: float,
                 assets: Dict, execution_time: int, witnesses: List[str] = None):
        self.will_id = will_id
        self.owner = owner
        self.heir = heir
        self.amount = amount
        self.assets = assets
        self.execution_time = execution_time
        self.created_at = int(time.time())
        self.executed = False
        self.witnesses = witnesses or []

    def to_dict(self) -> Dict:
        return {
            "will_id": self.will_id,
            "owner": self.owner[:16] + "...",
            "heir": self.heir[:16] + "...",
            "amount": self.amount,
            "assets": self.assets,
            "execution_time": self.execution_time,
            "created_at": self.created_at,
            "executed": self.executed,
            "witnesses_count": len(self.witnesses),
        }


class CryptoWillManager:
    """Manages crypto inheritance: create wills, auto-execute at scheduled time."""

    MIN_DELAY = 86400       # 1 day
    MAX_DELAY = 31_536_000  # 1 year

    def __init__(self, blockchain=None):
        self.wills: Dict[str, CryptoWill] = {}
        self.blockchain = blockchain
        self._lock = threading.Lock()
        self._monitor_thread = threading.Thread(
            target=self._check_wills_loop, daemon=True
        )
        self._monitor_thread.start()
        print("[CryptoWill] Manager initialized")

    def create_will(self, owner: str, heir: str, amount: float,
                    assets: Dict, execution_delay: int,
                    witnesses: List[str] = None) -> Optional[str]:
        execution_delay = max(self.MIN_DELAY, min(self.MAX_DELAY, execution_delay))
        if self.blockchain:
            balance = self.blockchain.get_balance(owner) if hasattr(self.blockchain, "get_balance") else 0
            if balance < amount:
                return None
        will_id = hashlib.sha256(
            f"{owner}{heir}{amount}{time.time()}".encode()
        ).hexdigest()[:16]
        execution_time = int(time.time()) + execution_delay
        will = CryptoWill(will_id, owner, heir, amount, assets,
                          execution_time, witnesses)
        with self._lock:
            self.wills[will_id] = will
        print(f"[CryptoWill] Created: {will_id} owner={owner[:12]}... "
              f"heir={heir[:12]}... amount={amount}")
        return will_id

    def get_will(self, will_id: str) -> Optional[Dict]:
        with self._lock:
            w = self.wills.get(will_id)
        return w.to_dict() if w else None

    def get_user_wills(self, address: str) -> List[Dict]:
        with self._lock:
            return [w.to_dict() for w in self.wills.values()
                    if w.owner == address or w.heir == address]

    def cancel_will(self, will_id: str, owner: str) -> bool:
        with self._lock:
            w = self.wills.get(will_id)
            if not w or w.owner != owner or w.executed:
                return False
            del self.wills[will_id]
        return True

    def get_stats(self) -> Dict:
        with self._lock:
            total = len(self.wills)
            executed = sum(1 for w in self.wills.values() if w.executed)
            pending = total - executed
            total_amount = sum(w.amount for w in self.wills.values() if not w.executed)
        return {
            "total_wills": total,
            "executed_wills": executed,
            "pending_wills": pending,
            "total_locked_amount": total_amount,
        }

    def _check_wills_loop(self):
        while True:
            time.sleep(3600)
            self._execute_due_wills()

    def _execute_due_wills(self):
        now = int(time.time())
        with self._lock:
            due = [w for w in self.wills.values()
                   if not w.executed and now >= w.execution_time]
        for w in due:
            self._execute_will(w)

    def _execute_will(self, will: CryptoWill):
        if will.executed:
            return
        if self.blockchain and hasattr(self.blockchain, "transfer"):
            try:
                self.blockchain.transfer(will.owner, will.heir, will.amount)
            except Exception:
                pass
        will.executed = True
        print(f"[CryptoWill] EXECUTED: {will.will_id} — "
              f"{will.amount} ABS → {will.heir[:12]}...")
