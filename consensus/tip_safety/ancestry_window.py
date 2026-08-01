"""Bounded tip ancestry window (ADR 0016 / tip-safety stage-1.5).

Records recent tip BlockRefs so reorg policy can verify parent linkage within
a finite window above the finalized floor. This is **not** a full DAG store
and **not** Long-Range / BFT tip proof.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Dict, Iterator, Optional

from consensus.tip_safety.types import BlockRef


class AncestryWindow:
    """Thread-safe LRU of recent blocks keyed by hash + height index.

    Invariant: at most ``max_blocks`` hashes retained. Heights may map to one
    canonical hash (last recorded wins for that height).
    """

    def __init__(self, max_blocks: int = 256) -> None:
        if int(max_blocks) < 1:
            raise ValueError("max_blocks must be >= 1")
        self._max = int(max_blocks)
        self._by_hash: "OrderedDict[str, BlockRef]" = OrderedDict()
        self._by_height: Dict[int, str] = {}
        self._lock = threading.RLock()

    @property
    def max_blocks(self) -> int:
        return self._max

    def __len__(self) -> int:
        with self._lock:
            return len(self._by_hash)

    def clear(self) -> None:
        with self._lock:
            self._by_hash.clear()
            self._by_height.clear()

    def record(self, block: BlockRef) -> None:
        """Insert or refresh ``block``; evict oldest when over capacity."""
        if not isinstance(block, BlockRef):
            raise TypeError(f"block must be BlockRef, got {type(block).__name__}")
        key = str(block.block_hash)
        with self._lock:
            if key in self._by_hash:
                self._by_hash.move_to_end(key)
                self._by_hash[key] = block
            else:
                self._by_hash[key] = block
            self._by_height[int(block.height)] = key
            while len(self._by_hash) > self._max:
                old_hash, old_ref = self._by_hash.popitem(last=False)
                h = int(old_ref.height)
                if self._by_height.get(h) == old_hash:
                    del self._by_height[h]

    def get(self, block_hash: str) -> Optional[BlockRef]:
        key = str(block_hash or "")
        if not key:
            return None
        with self._lock:
            ref = self._by_hash.get(key)
            if ref is not None:
                self._by_hash.move_to_end(key)
            return ref

    def get_at_height(self, height: int) -> Optional[BlockRef]:
        with self._lock:
            key = self._by_height.get(int(height))
            if not key:
                return None
            return self._by_hash.get(key)

    def contains(self, block_hash: str) -> bool:
        return self.get(block_hash) is not None

    def walk_parents(
        self, start: BlockRef, *, max_steps: Optional[int] = None
    ) -> Iterator[BlockRef]:
        """Yield ``start`` then parents while they remain in the window."""
        steps = self._max if max_steps is None else max(0, int(max_steps))
        cur: Optional[BlockRef] = start
        seen = set()
        for _ in range(steps):
            if cur is None:
                return
            h = str(cur.block_hash)
            if h in seen:
                return
            seen.add(h)
            yield cur
            parent = self.get(str(cur.parent_hash))
            cur = parent

    def connects_to(
        self,
        candidate: BlockRef,
        target_hash: str,
        *,
        max_steps: Optional[int] = None,
    ) -> bool:
        """True if walking parents from ``candidate`` reaches ``target_hash``."""
        want = str(target_hash or "")
        if not want:
            return False
        for ref in self.walk_parents(candidate, max_steps=max_steps):
            if str(ref.block_hash) == want:
                return True
            if str(ref.parent_hash) == want:
                return True
        return False

    def is_ancestor_of(
        self,
        descendant: BlockRef,
        ancestor_hash: str,
        *,
        max_steps: Optional[int] = None,
    ) -> bool:
        """True if ``ancestor_hash`` appears while walking parents from ``descendant``."""
        return self.connects_to(descendant, ancestor_hash, max_steps=max_steps)
