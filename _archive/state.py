#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Canonical Chain State - Single Source of Truth"""

import time
import hashlib
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from kernel.event_bus import bus

@dataclass
class Block:
    height: int
    block_hash: str
    previous_hash: str
    timestamp: int
    transactions: List[Dict]
    miner: str
    nonce: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "height": self.height,
            "block_hash": self.block_hash,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "miner": self.miner,
            "nonce": self.nonce
        }

class ChainState:
    """Single canonical chain state - ONLY NODE writes here"""
    
    def __init__(self):
        self.chain: List[Block] = []
        self.utxo_set: Dict[str, float] = {}
        self.pending_txs: List[Dict] = []
        self.last_block_time = time.time()
        
        # Genesis
        if not self.chain:
            self._create_genesis()
    
    def _create_genesis(self):
        """Create genesis block"""
        genesis = Block(
            height=0,
            block_hash="0x" + hashlib.sha256(b"genesis").hexdigest()[:40],
            previous_hash="0x" + "0" * 40,
            timestamp=int(time.time()),
            transactions=[],
            miner="system"
        )
        self.chain.append(genesis)
        bus.emit("GENESIS_CREATED", genesis.to_dict())
        print(f"[ChainState] Genesis block created at height 0")
    
    def create_block(self, transactions: List[Dict] = None) -> Block:
        """Create a new block - called by NODE"""
        prev_block = self.chain[-1]
        
        new_block = Block(
            height=prev_block.height + 1,
            block_hash="",
            previous_hash=prev_block.block_hash,
            timestamp=int(time.time()),
            transactions=transactions or [],
            miner="miner"
        )
        
        # Calculate hash
        block_data = f"{new_block.height}{new_block.previous_hash}{new_block.timestamp}{json.dumps(new_block.transactions)}"
        new_block.block_hash = "0x" + hashlib.sha256(block_data.encode()).hexdigest()[:40]
        
        return new_block
    
    def apply_block(self, block: Block) -> bool:
        """Apply block to state - ONLY NODE calls this"""
        # Validate
        if len(self.chain) > 0 and block.previous_hash != self.chain[-1].block_hash:
            print(f"[ChainState] Invalid block: wrong previous hash")
            return False
        
        # Apply transactions (UTXO updates)
        for tx in block.transactions:
            if tx["from"] != "coinbase":
                if tx["from"] in self.utxo_set:
                    if self.utxo_set[tx["from"]] >= tx["amount"]:
                        self.utxo_set[tx["from"]] -= tx["amount"]
                        self.utxo_set[tx["to"]] = self.utxo_set.get(tx["to"], 0) + tx["amount"]
        
        # Add to chain
        self.chain.append(block)
        
        # Emit event
        bus.emit("NEW_BLOCK", block.to_dict())
        bus.emit("STATE_UPDATED", {"height": block.height, "hash": block.block_hash})
        
        print(f"[ChainState] Block #{block.height} applied: {block.block_hash[:16]}...")
        return True
    
    def get_latest_block(self) -> Optional[Block]:
        """Get latest block"""
        return self.chain[-1] if self.chain else None
    
    def get_height(self) -> int:
        return len(self.chain) - 1
    
    def get_balance(self, address: str) -> float:
        return self.utxo_set.get(address, 0)

state = ChainState()
