#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Node Kernel - Single source of truth, only writer"""

import time
import threading
from kernel.state import state
from kernel.event_bus import bus

class NodeKernel:
    """
    Blockchain Node Kernel
    ONLY component that writes to state
    """
    
    def __init__(self, block_time: int = 15):
        self.block_time = block_time
        self.running = False
        self.miner_address = "0x" + "1" * 40
        self.last_block_time = time.time()
        
        # Subscribe to events
        bus.on("NEW_TRANSACTION", self.on_new_transaction)
        
    def start(self):
        """Start mining loop"""
        self.running = True
        print(f"[NodeKernel] Starting with block time: {self.block_time}s")
        
        thread = threading.Thread(target=self._mining_loop, daemon=True)
        thread.start()
        
    def _mining_loop(self):
        """Main mining loop"""
        while self.running:
            now = time.time()
            if now - self.last_block_time >= self.block_time:
                self.mine_block()
                self.last_block_time = now
            time.sleep(1)
    
    def on_new_transaction(self, tx_data):
        """Handle new transaction from mempool/API"""
        print(f"[NodeKernel] New tx received: {tx_data.get('from', 'unknown')[:16]}...")
        # Store in pending
        if not hasattr(self, 'pending_transactions'):
            self.pending_transactions = []
        self.pending_transactions.append(tx_data)
    
    def mine_block(self):
        """Create and apply a new block"""
        pending = getattr(self, 'pending_transactions', [])
        
        # Add coinbase transaction
        coinbase = {
            "from": "coinbase",
            "to": self.miner_address,
            "amount": 50.0,
            "fee": 0
        }
        
        transactions = [coinbase] + pending[-10:]  # Max 10 txs per block
        
        # Create block
        new_block = state.create_block(transactions)
        
        # Apply to state
        if state.apply_block(new_block):
            # Clear pending (except coinbase)
            self.pending_transactions = []
            
            # Emit block mined event
            bus.emit("BLOCK_MINED", new_block.to_dict())
            
            print(f"[NodeKernel] Mined block #{new_block.height}: {new_block.block_hash[:16]}...")
            
            return new_block
        
        return None
    
    def submit_transaction(self, tx: dict) -> bool:
        """Submit transaction to mempool"""
        bus.emit("NEW_TRANSACTION", tx)
        return True
    
    def get_status(self) -> dict:
        return {
            "running": self.running,
            "height": state.get_height(),
            "block_time": self.block_time,
            "pending_txs": len(getattr(self, 'pending_transactions', []))
        }

node = NodeKernel()
