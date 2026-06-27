# -*- coding: utf-8 -*-
"""Finality-safe reorg engine for legacy tests."""
from typing import Dict, List, Optional, Set


class ReorgEngine:
    def __init__(self):
        self._blocks: Dict[str, Dict] = {}
        self._head: Optional[str] = None
        self._finalized: Set[str] = set()

    def add_block(self, block_hash: str, parent: Optional[str], number: int) -> None:
        self._blocks[block_hash] = {"hash": block_hash, "parent": parent, "number": number}

    def set_head(self, block_hash: str) -> None:
        self._head = block_hash

    def get_head(self) -> Optional[str]:
        return self._head

    def set_finalized(self, block_hash: str) -> None:
        self._finalized.add(block_hash)

    def _chain_contains(self, tip: str, target: str) -> bool:
        current = tip
        visited = set()
        while current and current not in visited:
            if current == target:
                return True
            visited.add(current)
            current = self._blocks.get(current, {}).get("parent")
        return False

    def try_reorg(self, new_head: str) -> bool:
        if new_head not in self._blocks:
            return False
        for finalized in self._finalized:
            if not self._chain_contains(new_head, finalized):
                return False
        self._head = new_head
        return True

    def get_chain_from_head(self) -> List[str]:
        chain = []
        current = self._head
        visited = set()
        while current and current not in visited:
            chain.append(current)
            visited.add(current)
            current = self._blocks.get(current, {}).get("parent")
        return list(reversed(chain))

    def get_stats(self) -> Dict:
        return {
            "head": self._head,
            "finalized_blocks": sorted(self._finalized),
            "total_blocks": len(self._blocks),
        }
