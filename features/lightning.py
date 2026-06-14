"""Lightning Network — payment channels with SQLite persistence (Wave 40)."""

import hashlib
import time
from typing import Dict, List, Optional


class LightningChannel:
    def __init__(self, channel_id: str, node1: str, node2: str, capacity: float,
                 balance1: float = None, balance2: float = None,
                 status: str = "open", created_at: int = None, fee_rate: float = 0.00001):
        self.channel_id = channel_id
        self.node1 = node1
        self.node2 = node2
        self.capacity = capacity
        self.balance1 = balance1 if balance1 is not None else capacity / 2
        self.balance2 = balance2 if balance2 is not None else capacity / 2
        self.status = status
        self.created_at = created_at if created_at is not None else int(time.time())
        self.fee_rate = fee_rate

    def to_dict(self) -> Dict:
        return {
            "channel_id": self.channel_id,
            "node1": self.node1[:16] + "..." if len(self.node1) > 20 else self.node1,
            "node2": self.node2[:16] + "..." if len(self.node2) > 20 else self.node2,
            "capacity": self.capacity,
            "balance1": self.balance1,
            "balance2": self.balance2,
            "status": self.status,
            "created_at": self.created_at,
        }

    def to_db(self) -> Dict:
        return {
            "channel_id": self.channel_id,
            "node1": self.node1,
            "node2": self.node2,
            "capacity": self.capacity,
            "balance1": self.balance1,
            "balance2": self.balance2,
            "status": self.status,
            "created_at": self.created_at,
            "fee_rate": self.fee_rate,
        }


class LightningPayment:
    def __init__(self, payment_id: str, channel_id: str, from_node: str,
                 to_node: str, amount: float, fee: float,
                 timestamp: int = None, status: str = "completed"):
        self.payment_id = payment_id
        self.channel_id = channel_id
        self.from_node = from_node
        self.to_node = to_node
        self.amount = amount
        self.fee = fee
        self.timestamp = timestamp if timestamp is not None else int(time.time())
        self.status = status
        self.payment_hash = hashlib.sha256(
            f"{payment_id}{amount}{self.timestamp}".encode()
        ).hexdigest()

    def to_dict(self) -> Dict:
        return {
            "payment_id": self.payment_id[:16],
            "channel_id": self.channel_id[:16],
            "from": self.from_node[:16] + "...",
            "to": self.to_node[:16] + "...",
            "amount": self.amount,
            "fee": self.fee,
            "status": self.status,
            "timestamp": self.timestamp,
        }

    def to_db(self) -> Dict:
        return {
            "payment_id": self.payment_id,
            "channel_id": self.channel_id,
            "from_node": self.from_node,
            "to_node": self.to_node,
            "amount": self.amount,
            "fee": self.fee,
            "status": self.status,
            "payment_hash": self.payment_hash,
            "timestamp": self.timestamp,
        }


class LightningNetwork:
    """Payment channel network — locks L1 ABS on open, persists to SQLite."""

    MIN_CHANNEL = 1.0
    MAX_CHANNEL = 10_000.0

    def __init__(self, node_address: str = "genesis", db=None):
        self.node_address = node_address
        self.db = db
        self.channels: Dict[str, LightningChannel] = {}
        self.payments: Dict[str, LightningPayment] = {}
        self._load_from_db()
        print(f"[Lightning] Network initialized for {node_address[:16]}... "
              f"({len(self.channels)} channels, persisted={bool(db)})")

    def _load_from_db(self) -> None:
        if not self.db or not hasattr(self.db, "get_lightning_channels"):
            return
        for row in self.db.get_lightning_channels():
            ch = LightningChannel(
                channel_id=row["channel_id"],
                node1=row["node1"],
                node2=row["node2"],
                capacity=row["capacity"],
                balance1=row["balance1"],
                balance2=row["balance2"],
                status=row["status"],
                created_at=row["created_at"],
                fee_rate=row.get("fee_rate", 0.00001),
            )
            self.channels[ch.channel_id] = ch
        for row in self.db.get_lightning_payments(limit=500):
            p = LightningPayment(
                payment_id=row["payment_id"],
                channel_id=row["channel_id"],
                from_node=row["from_node"],
                to_node=row["to_node"],
                amount=row["amount"],
                fee=row["fee"],
                timestamp=row["timestamp"],
                status=row.get("status", "completed"),
            )
            self.payments[p.payment_id] = p

    def _persist_channel(self, ch: LightningChannel) -> None:
        if self.db and hasattr(self.db, "save_lightning_channel"):
            self.db.save_lightning_channel(ch.to_db())

    def _persist_payment(self, p: LightningPayment) -> None:
        if self.db and hasattr(self.db, "save_lightning_payment"):
            self.db.save_lightning_payment(p.to_db())

    def open_channel(self, peer_address: str, capacity: float,
                     node_balance: float = None) -> Optional[str]:
        if capacity < self.MIN_CHANNEL or capacity > self.MAX_CHANNEL:
            return None
        if self.db and hasattr(self.db, "get_balance"):
            bal = self.db.get_balance(self.node_address)
            if bal < capacity:
                return None
        elif node_balance is not None and node_balance < capacity:
            return None
        if self.db and hasattr(self.db, "update_balance"):
            self.db.update_balance(self.node_address, -capacity)
        channel_id = hashlib.sha256(
            f"{self.node_address}{peer_address}{capacity}{time.time()}".encode()
        ).hexdigest()[:16]
        ch = LightningChannel(channel_id, self.node_address, peer_address, capacity)
        self.channels[channel_id] = ch
        self._persist_channel(ch)
        return channel_id

    def close_channel(self, channel_id: str) -> bool:
        ch = self.channels.get(channel_id)
        if not ch or ch.status != "open":
            return False
        if self.db and hasattr(self.db, "update_balance"):
            self.db.update_balance(ch.node1, ch.balance1)
            self.db.update_balance(ch.node2, ch.balance2)
        ch.status = "closed"
        self._persist_channel(ch)
        return True

    def send_payment(self, channel_id: str, to_node: str,
                     amount: float) -> Optional[str]:
        ch = self.channels.get(channel_id)
        if not ch or ch.status != "open":
            return None
        if self.node_address == ch.node1:
            if ch.balance1 < amount:
                return None
            ch.balance1 -= amount
            ch.balance2 += amount
        elif self.node_address == ch.node2:
            if ch.balance2 < amount:
                return None
            ch.balance1 += amount
            ch.balance2 -= amount
        else:
            return None
        fee = amount * ch.fee_rate
        pid = hashlib.sha256(
            f"{channel_id}{self.node_address}{to_node}{amount}{time.time()}".encode()
        ).hexdigest()[:16]
        payment = LightningPayment(
            pid, channel_id, self.node_address, to_node, amount, fee
        )
        self.payments[pid] = payment
        self._persist_channel(ch)
        self._persist_payment(payment)
        return pid

    def get_channel_info(self, channel_id: str) -> Optional[Dict]:
        ch = self.channels.get(channel_id)
        return ch.to_dict() if ch else None

    def get_all_channels(self) -> List[Dict]:
        return [ch.to_dict() for ch in self.channels.values()]

    def get_payment_history(self, limit: int = 50) -> List[Dict]:
        payments = sorted(self.payments.values(), key=lambda p: p.timestamp, reverse=True)
        return [p.to_dict() for p in payments[:limit]]

    def get_stats(self) -> Dict:
        total_capacity = sum(ch.capacity for ch in self.channels.values())
        active = sum(1 for ch in self.channels.values() if ch.status == "open")
        total_paid = sum(p.amount for p in self.payments.values())
        return {
            "channels_count": len(self.channels),
            "active_channels": active,
            "total_capacity": total_capacity,
            "payments_count": len(self.payments),
            "total_volume": total_paid,
            "persisted": bool(self.db),
            "node_address": self.node_address,
        }
