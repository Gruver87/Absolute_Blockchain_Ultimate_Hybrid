# -*- coding: utf-8 -*-
"""Adversarial network simulator for legacy tests."""
import random
import time
from typing import Any, Dict, List, Optional, Tuple


class AdversarialNetwork:
    def __init__(self):
        self.nodes: set = set()
        self._latency: Dict[Tuple[str, str], Tuple[float, float]] = {}
        self.loss_rate = 0.0
        self._partitions: Optional[List[List[str]]] = None
        self._queue: List[Tuple[float, str, str, Any]] = []
        self._fake_blocks: Dict[str, List[Dict]] = {}

    def add_node(self, name: str) -> None:
        self.nodes.add(name)

    def set_latency(self, a: str, b: str, min_s: float, max_s: float) -> None:
        self._latency[(a, b)] = (min_s, max_s)

    def set_loss_rate(self, rate: float) -> None:
        self.loss_rate = max(0.0, min(1.0, rate))

    def partition(self, groups: List[List[str]]) -> None:
        self._partitions = [list(g) for g in groups]

    def clear_partition(self) -> None:
        self._partitions = None

    def is_connected(self, a: str, b: str) -> bool:
        if self._partitions is None:
            return True
        group_a = group_b = None
        for group in self._partitions:
            if a in group:
                group_a = group
            if b in group:
                group_b = group
        return group_a is not None and group_a is group_b

    def send(self, src: str, dst: str, message: Any) -> bool:
        if not self.is_connected(src, dst):
            return False
        if random.random() < self.loss_rate:
            return False
        delay = 0.0
        key = (src, dst)
        if key in self._latency:
            lo, hi = self._latency[key]
            delay = random.uniform(lo, hi)
        self._queue.append((time.time() + delay, src, dst, message))
        return True

    def process(self, now: Optional[float] = None) -> List[Tuple[str, str, Any]]:
        now = now if now is not None else time.time()
        delivered = []
        pending = []
        for due, src, dst, msg in self._queue:
            if due <= now:
                delivered.append((src, dst, msg))
            else:
                pending.append((due, src, dst, msg))
        self._queue = pending
        return delivered

    def inject_fake_block(self, node: str, block: Dict) -> None:
        self._fake_blocks.setdefault(node, []).append(block)

    def get_fake_blocks(self, node: str) -> List[Dict]:
        return list(self._fake_blocks.get(node, []))

    def get_stats(self) -> Dict:
        return {
            "nodes": sorted(self.nodes),
            "partitions": self._partitions or [],
            "loss_rate": self.loss_rate,
            "queued": len(self._queue),
        }
