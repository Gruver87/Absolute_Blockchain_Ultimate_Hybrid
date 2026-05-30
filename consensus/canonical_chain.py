# consensus/canonical_chain.py
"""
Canonical Chain Manager with fork and reorg support
"""

from typing import Dict, List, Optional


class CanonicalChain:
    """
    Manages the canonical (main) chain
    Supports fork detection and reorgs
    """
    
    def __init__(self, storage):
        self.storage = storage
        self.canonical_blocks: Dict[int, str] = {}  # height -> block_hash
        self.head_block: Optional[dict] = None
        self.head_hash: str = ""
        self.head_height: int = 0
    
    def add_block(self, block: dict) -> bool:
        """Add block to canonical chain if it extends the current head"""
        if block["number"] == self.head_height + 1:
            if block["parent_hash"] == self.head_hash:
                self._add_to_canonical(block)
                return True
        return False
    
    def _add_to_canonical(self, block: dict):
        """Add block to canonical chain"""
        self.canonical_blocks[block["number"]] = block["hash"]
        self.head_block = block
        self.head_hash = block["hash"]
        self.head_height = block["number"]
    
    def get_head(self) -> Optional[dict]:
        return self.head_block
    
    def get_head_height(self) -> int:
        return self.head_height
    
    def get_canonical_hash(self, height: int) -> Optional[str]:
        return self.canonical_blocks.get(height)
    
    def is_canonical(self, block: dict) -> bool:
        return self.get_canonical_hash(block["number"]) == block["hash"]
    
    def detect_fork(self, block: dict) -> bool:
        """Check if block creates a fork"""
        canonical_parent = self.get_canonical_hash(block["number"] - 1)
        return canonical_parent and canonical_parent != block["parent_hash"]
    
    def get_common_ancestor(self, block1: dict, block2: dict) -> Optional[dict]:
        """Find common ancestor of two blocks"""
        # Simplified: traverse back until we find match
        b1 = block1
        b2 = block2
        
        while b1 and b2 and b1["number"] != b2["number"]:
            if b1["number"] > b2["number"]:
                b1 = self.storage.get_block(b1["parent_hash"])
            else:
                b2 = self.storage.get_block(b2["parent_hash"])
        
        if b1 and b2 and b1["hash"] == b2["hash"]:
            return b1
        return None


class ReorgManager:
    """Manages chain reorganizations (reorgs)"""
    
    def __init__(self, canonical_chain, state_engine, storage):
        self.canonical = canonical_chain
        self.state = state_engine
        self.storage = storage
    
    def reorg_to_chain(self, new_head: dict) -> tuple[bool, str]:
        """
        Reorganize the chain to a new head
        Rolls back old chain, applies new chain
        """
        current_head = self.canonical.get_head()
        
        if not current_head:
            return False, "No current head"
        
        # Find common ancestor
        common = self.canonical.get_common_ancestor(current_head, new_head)
        
        if not common:
            return False, "No common ancestor found"
        
        # Rollback blocks from current head to common ancestor
        to_rollback = []
        block = current_head
        while block and block["hash"] != common["hash"]:
            to_rollback.append(block)
            block = self.storage.get_block(block["parent_hash"])
        
        # Blocks to apply (new chain from common to new head)
        to_apply = []
        block = new_head
        while block and block["hash"] != common["hash"]:
            to_apply.insert(0, block)  # Reverse order
            block = self.storage.get_block(block["parent_hash"])
        
        # Execute reorg
        try:
            # Rollback (restore state from checkpoint)
            checkpoint = self.storage.get_checkpoint(common["hash"])
            if checkpoint:
                self.state.state = checkpoint
            
            # Apply new blocks
            for block in to_apply:
                success, error = self.state.transition(block)
                if not success:
                    return False, f"Reorg failed at block {block['number']}: {error}"
            
            # Update canonical head
            self.canonical._add_to_canonical(new_head)
            
            return True, f"Reorg completed: rolled back {len(to_rollback)}, applied {len(to_apply)}"
            
        except Exception as e:
            return False, f"Reorg failed: {e}"
