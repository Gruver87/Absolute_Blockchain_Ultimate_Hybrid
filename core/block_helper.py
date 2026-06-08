# core/block_helper.py - Unified block creation
import time
import hashlib
from typing import List, Dict, Optional

def create_block(height: int, transactions: List[Dict], prev_hash: str, 
                 validator: str = "", timestamp: float = None) -> Dict:
    """Create a unified block dict with all required fields"""
    
    if timestamp is None:
        timestamp = time.time()
    
    block = {
        'height': height,
        'transactions': transactions,
        'prev_hash': prev_hash,
        'timestamp': timestamp,
        'validator': validator,
        'nonce': 0,
        'hash': None
    }
    
    # Calculate block hash
    block_string = f"{block['height']}{block['transactions']}{block['prev_hash']}{block['timestamp']}{block['validator']}{block['nonce']}"
    block['hash'] = hashlib.sha256(block_string.encode()).hexdigest()[:16]
    
    return block

def safe_get(block: Dict, key: str, default=0):
    """Safely get value from block dict"""
    return block.get(key, default) if isinstance(block, dict) else default

def block_to_dict(block) -> Dict:
    """Convert any block format to dict"""
    if isinstance(block, dict):
        return block
    elif hasattr(block, 'to_dict'):
        return block.to_dict()
    elif hasattr(block, '__dict__'):
        return {k: v for k, v in block.__dict__.items() if not k.startswith('_')}
    else:
        return {}
