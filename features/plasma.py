"""Plasma Chain — Layer 2 sidechain with deposit/exit/challenge mechanism."""

import hashlib
import json
import threading
import time
from typing import Dict, List, Optional


class PlasmaBlock:
    def __init__(self, block_id: int, parent_hash: str, transactions: List[Dict]):
        self.block_id = block_id
        self.parent_hash = parent_hash
        self.transactions = transactions
        self.created_at = int(time.time())
        self.block_hash = self._calc_hash()
        self.transaction_count = len(transactions)
        self.total_amount = sum(tx.get("amount", 0) for tx in transactions)

    def _calc_hash(self) -> str:
        tx_data = json.dumps(self.transactions, sort_keys=True)
        raw = f"{self.block_id}{self.parent_hash}{tx_data}{self.created_at}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def to_dict(self) -> Dict:
        return {
            "block_id": self.block_id,
            "block_hash": self.block_hash[:16] + "...",
            "parent_hash": self.parent_hash[:16] + "...",
            "transaction_count": self.transaction_count,
            "total_amount": self.total_amount,
            "created_at": self.created_at,
        }


class PlasmaChain:
    """
    Plasma sidechain:
    - deposit ABS from L1 → L2
    - fast L2 transactions
    - exit with 7-day challenge period
    """

    CHALLENGE_PERIOD = 7 * 86400  # 7 days in seconds

    def __init__(self, chain_id: str = "plasma_main", root_chain=None):
        self.chain_id = chain_id
        self.root_chain = root_chain
        self.blocks: List[PlasmaBlock] = []
        self.pending_txs: List[Dict] = []
        self.deposits: Dict[str, Dict] = {}
        self.exit_requests: Dict[str, Dict] = {}
        self._lock = threading.RLock()
        # genesis block
        genesis = PlasmaBlock(0, "0" * 64, [])
        self.blocks.append(genesis)
        threading.Thread(target=self._exit_monitor_loop, daemon=True).start()
        print(f"[Plasma] Chain '{chain_id}' initialized")

    def deposit(self, from_addr: str, amount: float,
                main_tx_hash: str = "") -> Optional[str]:
        if amount <= 0:
            return None
        if self.root_chain and hasattr(self.root_chain, "get_balance"):
            bal = self.root_chain.get_balance(from_addr)
            if bal < amount:
                return None
        deposit_id = hashlib.sha256(
            f"{from_addr}{amount}{main_tx_hash}{time.time()}".encode()
        ).hexdigest()[:16]
        with self._lock:
            self.deposits[deposit_id] = {
                "id": deposit_id,
                "from": from_addr,
                "amount": amount,
                "main_tx_hash": main_tx_hash or deposit_id,
                "created_at": int(time.time()),
                "status": "confirmed",
            }
            self.pending_txs.append({
                "type": "deposit",
                "from": from_addr,
                "to": from_addr,
                "amount": amount,
                "deposit_id": deposit_id,
                "timestamp": int(time.time()),
            })
        print(f"[Plasma] Deposit {deposit_id}: {amount} ABS from {from_addr[:12]}...")
        return deposit_id

    def submit_transaction(self, from_addr: str, to_addr: str,
                           amount: float) -> Optional[str]:
        if amount <= 0 or not from_addr or not to_addr:
            return None
        tx = {
            "hash": hashlib.sha256(
                f"{from_addr}{to_addr}{amount}{time.time()}".encode()
            ).hexdigest()[:16],
            "from": from_addr,
            "to": to_addr,
            "amount": amount,
            "timestamp": int(time.time()),
        }
        with self._lock:
            self.pending_txs.append(tx)
        return tx["hash"]

    def submit_block(self, proposer: str = "operator") -> Optional[Dict]:
        with self._lock:
            if not self.pending_txs:
                return None
            parent_hash = self.blocks[-1].block_hash if self.blocks else "0" * 64
            new_block = PlasmaBlock(
                len(self.blocks), parent_hash, list(self.pending_txs)
            )
            self.blocks.append(new_block)
            self.pending_txs.clear()
        print(f"[Plasma] Block #{new_block.block_id} by {proposer[:12]}... "
              f"txs={new_block.transaction_count}")
        return new_block.to_dict()

    def request_exit(self, deposit_id: str, user: str) -> Optional[str]:
        with self._lock:
            dep = self.deposits.get(deposit_id)
            if not dep or dep["status"] != "confirmed" or dep["from"] != user:
                return None
            exit_id = hashlib.sha256(
                f"{deposit_id}{user}{time.time()}".encode()
            ).hexdigest()[:16]
            self.exit_requests[exit_id] = {
                "id": exit_id,
                "deposit_id": deposit_id,
                "user": user,
                "amount": dep["amount"],
                "created_at": int(time.time()),
                "status": "pending",
            }
            dep["status"] = "exiting"
        return exit_id

    def finalize_exit(self, exit_id: str) -> bool:
        with self._lock:
            req = self.exit_requests.get(exit_id)
            if not req or req["status"] != "pending":
                return False
            if time.time() - req["created_at"] < self.CHALLENGE_PERIOD:
                return False
            req["status"] = "finalized"
            dep = self.deposits.get(req["deposit_id"])
            if dep:
                dep["status"] = "exited"
        print(f"[Plasma] Exit finalized: {exit_id} {req['amount']} ABS → {req['user'][:12]}...")
        return True

    def get_blocks(self, limit: int = 20) -> List[Dict]:
        with self._lock:
            return [b.to_dict() for b in self.blocks[-limit:]]

    def get_stats(self) -> Dict:
        with self._lock:
            total_deposited = sum(d["amount"] for d in self.deposits.values())
            total_withdrawn = sum(
                e["amount"] for e in self.exit_requests.values()
                if e["status"] == "finalized"
            )
            return {
                "chain_id": self.chain_id,
                "blocks": len(self.blocks),
                "pending_transactions": len(self.pending_txs),
                "total_deposits": len(self.deposits),
                "total_exits": len(self.exit_requests),
                "total_deposited": total_deposited,
                "total_withdrawn": total_withdrawn,
                "tvl": total_deposited - total_withdrawn,
            }

    def _exit_monitor_loop(self):
        while True:
            time.sleep(3600)
            with self._lock:
                pending = [eid for eid, e in self.exit_requests.items()
                           if e["status"] == "pending"]
            for eid in pending:
                self.finalize_exit(eid)
