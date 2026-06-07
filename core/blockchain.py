# core/blockchain.py - FIXED FOR DICT SUPPORT
import time
import hashlib
from typing import List, Dict, Optional


class Blockchain:
    """Blockchain with dict-based blocks for simplicity"""
    
    def __init__(self):
        self.chain: List[Dict] = []
        self.load_chain()
    
    def load_chain(self):
        """Load chain from storage (simplified - in-memory for now)"""
        # Try to load from file if needed
        pass
    
    def add_block(self, block: Dict) -> bool:
        """Add block to chain - works with dict blocks"""
        try:
            # Validate block
            if not isinstance(block, dict):
                print(f"   ⚠️ Block is not dict: {type(block)}")
                return False
            
            # Check height
            height = block.get('height', -1)
            if height < 0:
                return False
            
            # Check prev_hash
            prev_hash = block.get('prev_hash', '')
            if len(self.chain) > 0:
                last_block = self.chain[-1]
                last_hash = last_block.get('hash', '')
                if prev_hash != last_hash:
                    print(f"   ⚠️ Invalid prev_hash: {prev_hash[:8]} != {last_hash[:8]}")
                    return False
                
                if height != len(self.chain):
                    print(f"   ⚠️ Invalid height: {height} != {len(self.chain)}")
                    return False
            elif height != 0:
                # Genesis block must be height 0
                if 'genesis' not in block.get('validator', ''):
                    return False
            
            # Add to chain
            self.chain.append(block)
            return True
            
        except Exception as e:
            print(f"   ⚠️ Error adding block: {e}")
            return False
    
    def get_height(self) -> int:
        """Get current chain height"""
        return len(self.chain)
    
    def get_latest_block(self) -> Optional[Dict]:
        """Get latest block"""
        return self.chain[-1] if self.chain else None
    
    def get_block(self, height: int) -> Optional[Dict]:
        """Get block at height"""
        if 0 <= height < len(self.chain):
            return self.chain[height]
        return None
    
    def create_genesis_block(self) -> Dict:
        """Create genesis block"""
        genesis = {
            'height': 0,
            'transactions': [],
            'prev_hash': '0'*16,
            'timestamp': time.time(),
            'validator': 'genesis',
            'nonce': 0,
            'hash': hashlib.sha256(b'genesis').hexdigest()[:16]
        }
        return genesis
    
    def validate_chain(self) -> bool:
        """Validate entire chain"""
        for i, block in enumerate(self.chain):
            if i > 0:
                prev_block = self.chain[i-1]
                if block.get('prev_hash') != prev_block.get('hash'):
                    return False
                if block.get('height') != i:
                    return False
        return True
    
    def to_dict(self) -> Dict:
        """Export chain to dict"""
        return {
            'chain': self.chain,
            'height': self.get_height()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Blockchain':
        """Import chain from dict"""
        blockchain = cls()
        blockchain.chain = data.get('chain', [])
        return blockchain
