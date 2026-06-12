# execution/block_importer.py
"""
Block Importer — executes, validates, and imports blocks
"""

import copy
from typing import Dict, Any, Optional, List


class BlockImporter:
    """
    Imports blocks into the blockchain
    Validates → executes → commits → updates state
    """
    
    def __init__(self, state_engine, block_validator, storage):
        self.state = state_engine
        self.validator = block_validator
        self.storage = storage
        self.imported_blocks: List[dict] = []
    
    def import_block(self, block: dict, parent_block: Optional[dict] = None) -> tuple[bool, str]:
        """
        Full block import pipeline:
        1. Validate block
        2. Execute block (get new state)
        3. Validate state root
        4. Commit new state
        5. Save block
        """
        # Step 1: Validation
        valid, error = self.validator.validate_block(block, parent_block)
        if not valid:
            return False, f"Validation failed: {error}"
        
        # Step 2: Save current state for potential rollback
        old_state = copy.deepcopy(self.state.state)
        
        # Step 3: Execute block
        try:
            new_state = self.state.transition(block)
        except Exception as e:
            # Rollback state
            self.state.state = old_state
            return False, f"Execution failed: {e}"
        
        # Step 4: Validate state root
        if not self.validator.validate_state_root(block, new_state.state_root):
            self.state.state = old_state
            return False, "State root mismatch"
        
        # Step 5: Finalize block hash
        if not block.get("hash"):
            import hashlib, json
            block_data = json.dumps({
                "number": block["number"],
                "parent_hash": block["parent_hash"],
                "timestamp": block["timestamp"],
                "tx_root": block.get("tx_root", ""),
                "state_root": new_state.state_root
            }, sort_keys=True)
            block["hash"] = hashlib.sha256(block_data.encode()).hexdigest()[:32]
        
        block["state_root"] = new_state.state_root
        
        # Step 6: Save to storage
        self.storage.save_block(block["number"], block)
        self.imported_blocks.append(block)
        
        return True, "Block imported successfully"
    
    def import_chain(self, blocks: List[dict]) -> int:
        """Import multiple blocks sequentially"""
        imported = 0
        parent = None
        
        for block in blocks:
            success, _ = self.import_block(block, parent)
            if not success:
                break
            parent = block
            imported += 1
        
        return imported
    
    def get_last_imported_block(self) -> Optional[dict]:
        if not self.imported_blocks:
            return None
        return self.imported_blocks[-1]

# execution/block_importer.py (v50 reorg hook)

# Add this method to BlockImporter class:

def import_block_with_reorg(self, block: dict) -> tuple[bool, str]:
    """Import block with fork detection and reorg support"""
    
    # Basic validation
    valid, error = self.validator.validate_block(block)
    if not valid:
        return False, error
    
    # Fork detection
    current_tip = self.storage.get_latest_block()
    if current_tip and block.get("parent_hash") != current_tip.get("hash"):
        print(f"⚠️ Fork detected! Parent: {block.get('parent_hash')[:16]}... Tip: {current_tip.get('hash')[:16]}...")
        
        # Check if we already have the parent
        parent = self.storage.get_block(block.get("parent_hash"))
        if parent:
            # This is a side chain - trigger reorg if heavier
            return self._handle_fork(block, current_tip)
    
    # Normal import
    return self.import_block(block)

def _handle_fork(self, new_block: dict, current_tip: dict) -> tuple[bool, str]:
    """Handle chain fork - reorg if new chain is heavier"""
    
    # Simplified: compare heights
    # In production, use total difficulty or weight
    
    new_height = new_block.get("number", 0)
    current_height = current_tip.get("number", 0)
    
    if new_height > current_height:
        print(f"🔄 Reorg: switching from chain height {current_height} to {new_height}")
        # Here you would implement actual reorg logic
        return True, "Fork accepted (higher height)"
    else:
        return False, "Fork rejected (shorter chain)"
