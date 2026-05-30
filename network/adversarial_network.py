# network/adversarial_network.py
"""
Adversarial Network Simulator — hostile network conditions
- Message delays
- Network partitions
- Fork injection attacks
"""

import random
import time
from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple, Optional


class AdversarialNetwork:
    """
    Simulates real-world hostile network conditions:
    - message delays
    - message loss
    - partitions
    - fork injection
    """

    def __init__(self):
        self.nodes: Set[str] = set()
        self.partitions: List[Set[str]] = []  # isolated network groups
        self.latency: Dict[Tuple[str, str], Tuple[float, float]] = {}
        self.message_queue: deque = deque()
        self.loss_rate: float = 0.0  # 0-1 probability of message loss
        self.fake_blocks: Dict[str, List[dict]] = defaultdict(list)

    def add_node(self, node_id: str):
        self.nodes.add(node_id)

    def remove_node(self, node_id: str):
        self.nodes.discard(node_id)

    def set_latency(self, node_a: str, node_b: str, min_delay: float, max_delay: float):
        """Set latency range between two nodes (seconds)"""
        self.latency[(node_a, node_b)] = (min_delay, max_delay)
        self.latency[(node_b, node_a)] = (min_delay, max_delay)

    def set_loss_rate(self, rate: float):
        """Set probability of message loss (0-1)"""
        self.loss_rate = max(0.0, min(1.0, rate))

    def partition(self, groups: List[List[str]]):
        """
        Split network into isolated groups
        Example: partition([["A","B"], ["C","D"]]) creates two isolated groups
        """
        self.partitions = [set(group) for group in groups]

    def clear_partition(self):
        """Remove all partitions (network heals)"""
        self.partitions = []

    def is_connected(self, node_a: str, node_b: str) -> bool:
        """Check if two nodes can communicate"""
        if not self.partitions:
            return True
        for group in self.partitions:
            if node_a in group and node_b in group:
                return True
        return False

    def send(self, from_node: str, to_node: str, message: dict) -> bool:
        """
        Send message with simulated network conditions
        Returns True if message accepted, False if dropped
        """
        if from_node not in self.nodes or to_node not in self.nodes:
            return False

        # Check partition
        if not self.is_connected(from_node, to_node):
            return False

        # Check message loss
        if random.random() < self.loss_rate:
            return False

        # Calculate delay
        key = (from_node, to_node)
        if key in self.latency:
            min_d, max_d = self.latency[key]
            delay = random.uniform(min_d, max_d)
        else:
            delay = random.uniform(0.01, 0.1)  # default 10-100ms

        # Queue message for delivery
        self.message_queue.append({
            "from": from_node,
            "to": to_node,
            "msg": message,
            "deliver_at": time.time() + delay
        })
        return True

    def process(self, current_time: float) -> List[dict]:
        """
        Process message queue, return delivered messages
        """
        delivered = []
        temp_queue = []

        while self.message_queue:
            msg = self.message_queue.popleft()
            if msg["deliver_at"] <= current_time:
                delivered.append(msg)
            else:
                temp_queue.append(msg)

        self.message_queue.extend(temp_queue)
        return delivered

    def inject_fake_block(self, target_node: str, block: dict):
        """
        Attacker injects conflicting block into network
        """
        self.fake_blocks[target_node].append(block)

    def get_fake_blocks(self, node_id: str) -> List[dict]:
        """Get fake blocks for a node"""
        return self.fake_blocks.get(node_id, [])

    def clear_fake_blocks(self):
        self.fake_blocks.clear()

    def get_stats(self) -> dict:
        return {
            "nodes": len(self.nodes),
            "partitions": len(self.partitions),
            "partitions_detail": [list(p) for p in self.partitions],
            "message_queue_size": len(self.message_queue),
            "loss_rate": self.loss_rate,
            "fake_blocks_injected": sum(len(v) for v in self.fake_blocks.values())
        }
