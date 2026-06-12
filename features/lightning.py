"""Lightning Network — payment channels for instant off-chain transactions."""

import hashlib
import time
from typing import Dict, List, Optional


class LightningChannel:
    def __init__(self, channel_id: str, node1: str, node2: str, capacity: float):
        self.channel_id = channel_id
        self.node1 = node1
        self.node2 = node2
        self.capacity = capacity
        self.balance1 = capacity / 2
        self.balance2 = capacity / 2
        self.status = "open"
        self.created_at = int(time.time())
        self.fee_rate = 0.00001

    def to_dict(self) -> Dict:
        return {
            "channel_id": self.channel_id,
            "node1": self.node1[:16] + "...",
            "node2": self.node2[:16] + "...",
            "capacity": self.capacity,
            "balance1": self.balance1,
            "balance2": self.balance2,
            "status": self.status,
            "created_at": self.created_at,
        }


class LightningPayment:
    def __init__(self, payment_id: str, channel_id: str, from_node: str,
                 to_node: str, amount: float, fee: float):
        self.payment_id = payment_id
        self.channel_id = channel_id
        self.from_node = from_node
        self.to_node = to_node
        self.amount = amount
        self.fee = fee
        self.timestamp = int(time.time())
        self.status = "completed"
        self.payment_hash = hashlib.sha256(
            f"{payment_id}{amount}{time.time()}".encode()
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


class LightningNetwork:
    """Payment channel network for instant off-chain ABS transfers."""

    MIN_CHANNEL = 1.0
    MAX_CHANNEL = 10_000.0

    def __init__(self, node_address: str = "genesis"):
        self.node_address = node_address
        self.channels: Dict[str, LightningChannel] = {}
        self.payments: Dict[str, LightningPayment] = {}
        print(f"[Lightning] Network initialized for {node_address[:16]}...")

    def open_channel(self, peer_address: str, capacity: float,
                     node_balance: float = None) -> Optional[str]:
        if capacity < self.MIN_CHANNEL or capacity > self.MAX_CHANNEL:
            return None
        if node_balance is not None and node_balance < capacity:
            return None
        channel_id = hashlib.sha256(
            f"{self.node_address}{peer_address}{capacity}{time.time()}".encode()
        ).hexdigest()[:16]
        ch = LightningChannel(channel_id, self.node_address, peer_address, capacity)
        self.channels[channel_id] = ch
        return channel_id

    def close_channel(self, channel_id: str) -> bool:
        ch = self.channels.get(channel_id)
        if not ch or ch.status != "open":
            return False
        ch.status = "closed"
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
        self.payments[pid] = LightningPayment(
            pid, channel_id, self.node_address, to_node, amount, fee
        )
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
        }
