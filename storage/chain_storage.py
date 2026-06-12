# storage/chain_storage.py
"""
Persistent storage for blocks and state
"""

import json
import os
import time
from typing import Optional, Dict, Any, List  # <-- ДОБАВЛЕН импорт List

class ChainStorage:
    """Persistent blockchain storage"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.blocks_dir = os.path.join(data_dir, "blocks")
        self.state_dir = os.path.join(data_dir, "state")
        self.checkpoints_dir = os.path.join(data_dir, "checkpoints")
        
        os.makedirs(self.blocks_dir, exist_ok=True)
        os.makedirs(self.state_dir, exist_ok=True)
        os.makedirs(self.checkpoints_dir, exist_ok=True)
    
    def save_block(self, number: int, block: dict) -> bool:
        path = os.path.join(self.blocks_dir, f"{number}.json")
        try:
            with open(path, "w") as f:
                json.dump(block, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving block {number}: {e}")
            return False
    
    def get_block(self, number: int) -> Optional[dict]:
        path = os.path.join(self.blocks_dir, f"{number}.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
        return None
    
    def get_block_by_hash(self, block_hash: str) -> Optional[dict]:
        for filename in os.listdir(self.blocks_dir):
            if filename.endswith(".json"):
                with open(os.path.join(self.blocks_dir, filename), "r") as f:
                    block = json.load(f)
                    if block.get("hash") == block_hash:
                        return block
        return None
    
    def get_latest_block(self) -> Optional[dict]:
        max_num = -1
        latest = None
        for filename in os.listdir(self.blocks_dir):
            if filename.endswith(".json"):
                try:
                    num = int(filename.replace(".json", ""))
                    if num > max_num:
                        max_num = num
                        with open(os.path.join(self.blocks_dir, filename), "r") as f:
                            latest = json.load(f)
                except:
                    pass
        return latest
    
    def get_block_count(self) -> int:
        return len([f for f in os.listdir(self.blocks_dir) if f.endswith(".json")])
    
    def save_state(self, block_hash: str, state: dict) -> bool:
        path = os.path.join(self.state_dir, f"{block_hash}.json")
        try:
            with open(path, "w") as f:
                json.dump(state, f, indent=2)
            return True
        except:
            return False
    
    def get_state(self, block_hash: str) -> Optional[dict]:
        path = os.path.join(self.state_dir, f"{block_hash}.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
        return None
    
    def save_checkpoint(self, block_hash: str, checkpoint: dict) -> bool:
        path = os.path.join(self.checkpoints_dir, f"{block_hash}.json")
        try:
            with open(path, "w") as f:
                json.dump(checkpoint, f, indent=2)
            return True
        except:
            return False
    
    def get_checkpoint(self, block_hash: str) -> Optional[dict]:
        path = os.path.join(self.checkpoints_dir, f"{block_hash}.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
        return None
    
    def get_stats(self) -> dict:
        return {
            "total_blocks": self.get_block_count(),
            "state_snapshots": len(os.listdir(self.state_dir)) if os.path.exists(self.state_dir) else 0,
            "checkpoints": len(os.listdir(self.checkpoints_dir)) if os.path.exists(self.checkpoints_dir) else 0,
            "data_dir": self.data_dir
        }
    
    def replace_chain(self, new_blocks: List[dict]) -> bool:
        """Replace entire chain (for reorg)"""
        try:
            # Clear existing blocks
            for filename in os.listdir(self.blocks_dir):
                if filename.endswith(".json"):
                    os.remove(os.path.join(self.blocks_dir, filename))
            
            # Save new blocks
            for block in new_blocks:
                self.save_block(block.get("number", 0), block)
            
            print(f"[CHAIN] Chain replaced with {len(new_blocks)} blocks")
            return True
        except Exception as e:
            print(f"Error replacing chain: {e}")
            return False
