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
