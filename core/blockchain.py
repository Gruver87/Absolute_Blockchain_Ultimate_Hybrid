# core/blockchain.py - WITH PERSISTENT STORAGE
import json
import os
import hashlib
import time
from typing import List, Dict, Optional

class Blockchain:
    """Blockchain with persistent SQLite storage"""
    
    def __init__(self, db_path: str = "data/blockchain.db"):
        self.db_path = db_path
        self.chain: List[Dict] = []
        self._load_chain()
        
        if len(self.chain) == 0:
            genesis = self.create_genesis_block()
            self.add_block(genesis)
            self._save_chain()
    
    def _load_chain(self):
        """Load chain from file"""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r') as f:
                    data = json.load(f)
                    self.chain = data.get('chain', [])
                print(f"📦 Loaded chain: {len(self.chain)} blocks")
            except:
                self.chain = []
        else:
            self.chain = []
    
    def _save_chain(self):
        """Save chain to file"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with open(self.db_path, 'w') as f:
            json.dump({'chain': self.chain, 'timestamp': time.time()}, f, indent=2)
    
    def create_genesis_block(self) -> Dict:
        """Create genesis block"""
        return {
            'height': 0,
            'transactions': [],
            'prev_hash': '0'*16,
            'timestamp': time.time(),
            'validator': 'genesis',
            'nonce': 0,
            'hash': hashlib.sha256(b'genesis').hexdigest()[:16]
        }
    
    def add_block(self, block: Dict) -> bool:
        """Add block to chain and save"""
        try:
            # Validate
            if len(self.chain) > 0:
                last = self.chain[-1]
                if block.get('prev_hash') != last.get('hash'):
                    return False
                if block.get('height') != last.get('height') + 1:
                    return False
            
            self.chain.append(block)
            self._save_chain()  # SAVE IMMEDIATELY!
            return True
        except Exception as e:
            print(f"Error adding block: {e}")
            return False
    
    def get_height(self) -> int:
        return len(self.chain)
    
    def get_latest_block(self) -> Optional[Dict]:
        return self.chain[-1] if self.chain else None
    
    def get_block(self, height: int) -> Optional[Dict]:
        if 0 <= height < len(self.chain):
            return self.chain[height]
        return None
