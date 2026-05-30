# node_persistent.py (with RPC)
"""
Restartable Blockchain Node with Persistence and JSON-RPC
"""

import sys
import os
import time
import signal
from typing import Optional, Dict, List, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crypto.wallet import Wallet
from crypto.signing import Signer
from crypto.hashing import Hasher

from execution.state_engine import StateEngine
from execution.mempool import Mempool

from storage.persistent_storage import PersistentStorage

# Import RPC server
from rpc.server import JSONRPCServer


class PersistentNode:
    """Blockchain node with persistent storage, crash recovery, and JSON-RPC"""
    
    def __init__(self, data_dir: str = "data", rpc_port: int = 8545):
        self.data_dir = data_dir
        self.rpc_port = rpc_port
        self.running = False
        
        # Persistent storage
        self.storage = PersistentStorage(data_dir)
        
        # Recover from previous state
        self._recover_state()
        
        # Create or load wallet
        self.wallet = self._load_or_create_wallet()
        
        # Components
        self.state_engine = StateEngine()
        self.mempool = Mempool()
        
        # Peer manager (simplified)
        self.peer_manager = None
        
        # Load chain state
        self._load_chain_state()
        
        # JSON-RPC server
        self.rpc_server = JSONRPCServer(self, port=rpc_port)
        
        print(f"🆔 Node initialized")
        print(f"💰 Wallet: {self.wallet.address}")
        print(f"📊 Chain height: {self.storage.get_latest_block_number()}")
    
    def _recover_state(self):
        """Recover from crash"""
        print("🔍 Checking for previous state...")
        
        if self.storage.chain_exists():
            print("✅ Found existing chain, recovering...")
            self.storage.recover_from_crash()
            
            snapshot = self.storage.restore_from_snapshot()
            if snapshot:
                print(f"📸 Restored from snapshot at height {snapshot['height']}")
        else:
            print("🌍 No existing chain, will create genesis")
    
    def _load_or_create_wallet(self) -> Wallet:
        """Load existing wallet or create new"""
        wallet_path = f"{self.data_dir}/wallet.json"
        
        if os.path.exists(wallet_path):
            try:
                wallet = Wallet.import_wallet(wallet_path, password="")
                print(f"🔓 Loaded existing wallet: {wallet.address}")
                return wallet
            except:
                pass
        
        wallet = Wallet.create_new()
        wallet.export(wallet_path, password="")
        print(f"🆕 Created new wallet: {wallet.address}")
        return wallet
    
    def _load_chain_state(self):
        """Load chain state from storage"""
        latest_block = self.storage.get_latest_block()
        
        if latest_block:
            print(f"📦 Loading chain from block #{latest_block['number']}")
        else:
            print("🌍 Creating genesis block...")
            self._create_genesis()
    
    def _create_genesis(self):
        """Create genesis block and initial state"""
        genesis_state = self.state_engine.create_genesis({
            self.wallet.address: 1000000,
            "validator_foundation": 10000000
        })
        
        genesis_block = {
            "number": 0,
            "hash": genesis_state.block_hash,
            "parent_hash": "0" * 64,
            "timestamp": int(time.time()),
            "proposer": self.wallet.address,
            "state_root": genesis_state.state_root,
            "tx_root": Hasher.hash_object([])
        }
        
        self.storage.save_block(genesis_block)
        self.storage.save_account_state(self.wallet.address, 1000000, 0)
        self.storage.save_metadata("head_hash", genesis_block["hash"])
        self.storage.save_metadata("chain_id", "1337")
        
        print("✅ Genesis block created")
    
    def produce_block(self) -> Optional[dict]:
        """Produce a new block"""
        try:
            parent_block = self.storage.get_latest_block()
            if not parent_block:
                return None
            
            pending = self.mempool.get_sorted_transactions(limit=50)
            
            block = {
                "number": parent_block["number"] + 1,
                "parent_hash": parent_block["hash"],
                "timestamp": int(time.time()),
                "proposer": self.wallet.address,
                "transactions": [self._tx_to_dict(tx) for tx in pending],
                "tx_root": Hasher.hash_object([tx.hash for tx in pending]),
                "state_root": "",
                "signature": "",
                "public_key": self.wallet.public_key
            }
            
            block["state_root"] = Hasher.hash_object(block)
            block["signature"] = self.wallet.sign_block(block)
            block["hash"] = Hasher.hash_block(block)
            
            if self.storage.save_block(block):
                for tx in pending:
                    self.mempool.remove_transaction(tx.hash)
                
                for tx in pending:
                    self.storage.update_balance(tx.from_addr, -tx.value)
                    self.storage.update_balance(tx.to_addr, tx.value)
                
                self.storage.save_metadata("head_hash", block["hash"])
                
                print(f"📦 Block #{block['number']}: {block['hash'][:16]}... | {len(pending)} txs")
                return block
            
        except Exception as e:
            print(f"❌ Block production error: {e}")
        
        return None
    
    def _tx_to_dict(self, tx) -> dict:
        return {
            "hash": tx.hash,
            "from": tx.from_addr,
            "to": tx.to_addr,
            "value": tx.value,
            "nonce": tx.nonce
        }
    
    def send_transaction(self, to_addr: str, value: int) -> str:
        nonce = self.storage.get_nonce(self.wallet.address)
        tx = self.wallet.sign_transaction(to_addr, value, nonce)
        
        from execution.mempool import create_transaction
        tx_obj = create_transaction(tx["from"], tx["to"], tx["value"], nonce=tx["nonce"])
        tx_obj.hash = tx["hash"]
        tx_obj.signature = tx["signature"]
        
        self.mempool.add_transaction(tx_obj)
        print(f"📤 Transaction sent: {tx['hash'][:16]}...")
        return tx["hash"]
    
    def get_balance(self) -> int:
        return self.storage.get_balance(self.wallet.address)
    
    def get_stats(self) -> dict:
        return {
            "address": self.wallet.address,
            "balance": self.get_balance(),
            "height": self.storage.get_latest_block_number(),
            "mempool_size": self.mempool.get_pending_count(),
            "total_blocks": self.storage.get_stats()["total_blocks"]
        }
    
    def start(self, auto_mine: bool = True):
        """Start the node"""
        self.running = True
        
        # Start JSON-RPC server
        self.rpc_server.start()
        
        print(f"\n🚀 Node started!")
        print(f"   Address: {self.wallet.address}")
        print(f"   Balance: {self.get_balance()}")
        print(f"   Height: {self.storage.get_latest_block_number()}")
        print(f"   RPC: http://localhost:{self.rpc_port}")
        print("")
        
        if auto_mine:
            print("⛏️  Auto-mining enabled (block every 15 seconds)")
            
            def mine_loop():
                while self.running:
                    time.sleep(15)
                    self.produce_block()
            
            import threading
            mining_thread = threading.Thread(target=mine_loop, daemon=True)
            mining_thread.start()
        
        try:
            while self.running:
                cmd = input("\n> ").strip().lower()
                if cmd == "stats" or cmd == "s":
                    stats = self.get_stats()
                    print(f"📊 Stats: {stats}")
                elif cmd == "balance" or cmd == "b":
                    print(f"💰 Balance: {self.get_balance()}")
                elif cmd == "rpc" or cmd == "r":
                    print(f"🌐 RPC: http://localhost:{self.rpc_port}")
                elif cmd == "stop" or cmd == "exit":
                    self.stop()
                elif cmd == "help" or cmd == "h":
                    print("Commands: stats, balance, rpc, stop, help")
                else:
                    print("Unknown command. Type 'help'")
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        """Stop the node"""
        print("\n🛑 Stopping node...")
        self.running = False
        if hasattr(self, 'rpc_server'):
            self.rpc_server.stop()
        print("✅ Node stopped")


def main():
    print("=" * 60)
    print("ABSOLUTE BLOCKCHAIN NODE v48")
    print("Persistent Storage + Crash Recovery + JSON-RPC")
    print("=" * 60)
    print("")
    
    node = PersistentNode()
    node.start()


if __name__ == "__main__":
    main()
