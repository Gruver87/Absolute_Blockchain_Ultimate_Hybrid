# consensus/reorg_engine.py
"""
Reorg Engine с поддержкой state rollback
"""

from typing import Dict, Set, Optional, Any


class ReorgEngine:
    """
    Handles safe chain reorganizations with state rollback
    """

    def __init__(self, state_engine=None):
        self.finalized_blocks: Set[str] = set()
        self.justified_blocks: Set[str] = set()
        self.current_head: Optional[str] = None
        self.chain: Dict[str, Dict] = {}
        self.state_engine = state_engine

    def set_state_engine(self, state_engine):
        self.state_engine = state_engine

    def add_block(self, block_hash: str, parent_hash: Optional[str], number: int):
        self.chain[block_hash] = {
            "parent": parent_hash,
            "number": number,
            "children": []
        }
        if parent_hash and parent_hash in self.chain:
            self.chain[parent_hash].setdefault("children", []).append(block_hash)

    def set_finalized(self, block_hash: str):
        self.finalized_blocks.add(block_hash)
        print(f"🔒 Block {block_hash[:8]}... FINALIZED")

    def set_justified(self, block_hash: str):
        self.justified_blocks.add(block_hash)

    def set_head(self, block_hash: str):
        self.current_head = block_hash

    def get_head(self) -> Optional[str]:
        return self.current_head

    def can_reorg(self, new_head: str, old_head: str) -> bool:
        # Проверяем, что новый head не нарушает финализированные блоки
        current = new_head
        path_to_new = set()

        while current:
            path_to_new.add(current)
            if current in self.finalized_blocks:
                break
            current = self.chain.get(current, {}).get("parent")

        # Все финализированные блоки должны быть в новой цепи
        for finalized in self.finalized_blocks:
            if finalized not in path_to_new:
                # Проверяем, является ли finalized предком new_head
                temp = new_head
                found = False
                while temp:
                    if temp == finalized:
                        found = True
                        break
                    temp = self.chain.get(temp, {}).get("parent")
                if not found:
                    return False

        return True

    def try_reorg(self, new_head: str) -> bool:
        old_head = self.current_head

        if old_head is None:
            self.current_head = new_head
            return True

        if old_head == new_head:
            return True

        if not self.can_reorg(new_head, old_head):
            print(f"❌ REORG BLOCKED! Cannot reorg past finalized blocks")
            return False

        # При реорганизации нужно откатить состояние до общего предка
        if self.state_engine:
            # Находим общий предок
            ancestor = self._find_common_ancestor(old_head, new_head)
            if ancestor and ancestor in self.chain:
                # Откатываем состояние до предка
                self.state_engine.rollback_to_checkpoint(ancestor)
                print(f"🔄 State rolled back to ancestor {ancestor[:8]}...")

        self.current_head = new_head
        print(f"🔄 REORG executed: {old_head[:8]}... → {new_head[:8]}...")
        return True

    def _find_common_ancestor(self, block_a: str, block_b: str) -> Optional[str]:
        """Находит общий предок двух блоков"""
        path_a = set()
        current = block_a
        while current:
            path_a.add(current)
            current = self.chain.get(current, {}).get("parent")

        current = block_b
        while current:
            if current in path_a:
                return current
            current = self.chain.get(current, {}).get("parent")

        return None

    def is_finalized(self, block_hash: str) -> bool:
        return block_hash in self.finalized_blocks

    def get_chain_from_head(self) -> list:
        if not self.current_head:
            return []

        chain = []
        current = self.current_head
        while current:
            chain.append(current)
            current = self.chain.get(current, {}).get("parent")
        return list(reversed(chain))

    def get_stats(self) -> dict:
        return {
            "head": self.current_head[:8] + "..." if self.current_head else None,
            "finalized_blocks": len(self.finalized_blocks),
            "justified_blocks": len(self.justified_blocks),
            "total_blocks": len(self.chain),
            "has_state_engine": self.state_engine is not None
        }
