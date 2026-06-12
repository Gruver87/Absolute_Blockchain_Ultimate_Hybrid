# ============================================================
# ABSOLUTE BLOCKCHAIN - FIX IMPORTS AND PACKAGE STRUCTURE
# ============================================================

$ProjectPath = "C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate"
Set-Location $ProjectPath

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "FIXING PYTHON PACKAGE STRUCTURE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================
# 1. СОЗДАНИЕ ВСЕХ __init__.py
# ============================================================
Write-Host "[1/4] Creating __init__.py files..." -ForegroundColor Yellow

$initDirs = @(
    "core",
    "core/consensus",
    "core/state",
    "core/execution",
    "core/blockchain",
    "network",
    "network/p2p",
    "network/sync",
    "crypto",
    "rpc",
    "db",
    "node"
)

foreach ($dir in $initDirs) {
    $initFile = "$dir/__init__.py"
    if (!(Test-Path $initFile)) {
        Set-Content -Path $initFile -Value '# Package module' -Encoding UTF8
        Write-Host "   [OK] Created: $initFile" -ForegroundColor Green
    } else {
        Write-Host "   [SKIP] Already exists: $initFile" -ForegroundColor DarkGray
    }
}

# ============================================================
# 2. ИСПРАВЛЕНИЕ main.py
# ============================================================
Write-Host ""
Write-Host "[2/4] Fixing main.py imports..." -ForegroundColor Yellow

$fixedMain = @'
#!/usr/bin/env python3
"""
ABSOLUTE BLOCKCHAIN - FULL EXECUTION CLIENT
Enterprise-grade blockchain node with real architecture
"""

import sys
import os
import threading
import time
import signal

# Fix path for package imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))

# Now imports will work
from core.blockchain.block import Blockchain
from core.state.state_db import state_db
from core.execution.transaction import TransactionPool
from core.execution.engine import execution_engine
from core.consensus.consensus import ConsensusEngine
from crypto.crypto import crypto

# Import RPC and P2P
from rpc.rpc_server import start_rpc
from network.p2p.p2p import P2PNode

class FullNode:
    """Complete blockchain node with all components"""
    
    def __init__(self):
        self.blockchain = Blockchain()
        self.tx_pool = TransactionPool()
        self.consensus = ConsensusEngine()
        self.running = False
        
        # Generate or load wallet
        self._init_wallet()
    
    def _init_wallet(self):
        """Initialize node wallet"""
        import json
        os.makedirs("data", exist_ok=True)
        
        if os.path.exists("data/wallet.json"):
            with open("data/wallet.json", "r") as f:
                wallet = json.load(f)
                self.address = wallet["address"]
                print(f"[Node] Loaded wallet: {self.address}")
        else:
            priv, pub, addr = crypto.generate_keypair()
            self.address = addr
            with open("data/wallet.json", "w") as f:
                json.dump({"address": addr, "public_key": pub}, f)
            print(f"[Node] Created wallet: {self.address}")
        
        # Give initial balance to validator
        state_db.update_account(self.address, 100_000_000_000_000_000_000, 0)
    
    def mine_block(self):
        """Mine a new block (produce block every 15 seconds)"""
        # Get transactions from mempool
        txs = self.tx_pool.get_ordered(100)
        tx_list = [tx.to_dict() for tx in txs]
        
        if tx_list:
            print(f"[Miner] Processing {len(tx_list)} transactions")
        
        # Execute all transactions
        result = execution_engine.process_block(tx_list, self.address)
        
        # Create block
        latest = self.blockchain.latest_block()
        from core.blockchain.block import BlockHeader, Block
        
        header = BlockHeader(
            parent_hash=latest.hash() if latest else "0" * 64,
            timestamp=int(time.time()),
            number=self.blockchain.height() + 1,
            state_root=result["state_root"],
            tx_root=hash(str(tx_list)),
            miner=self.address,
            nonce=0
        )
        
        block = Block(header=header, transactions=tx_list)
        
        # Add to blockchain
        if self.blockchain.add_block(block):
            # Remove processed transactions from pool
            for tx in txs:
                self.tx_pool.remove(tx.hash())
            
            print(f"[Miner] Block #{block.header.number} mined!")
            print(f"       Hash: {block.hash()[:16]}...")
            print(f"       Txs: {len(tx_list)}")
            print(f"       State Root: {result['state_root'][:16]}...")
            
            return block
        return None
    
    def run(self):
        """Main node loop"""
        self.running = True
        print("="*60)
        print("ABSOLUTE BLOCKCHAIN - EXECUTION CLIENT")
        print("="*60)
        print(f"Node Address: {self.address}")
        print(f"Chain Height: {self.blockchain.height()}")
        print(f"State Root:   {state_db.state_root()[:16]}...")
        print("="*60)
        print("Starting services...")
        print("")
        
        # Start RPC server in thread
        rpc_thread = threading.Thread(target=start_rpc, args=("0.0.0.0", 8080), daemon=True)
        rpc_thread.start()
        print("[✓] RPC Server started on port 8080")
        
        # Start P2P in thread
        p2p_node = P2PNode(port=8546)
        p2p_thread = threading.Thread(target=p2p_node.start, daemon=True)
        p2p_thread.start()
        print("[✓] P2P Network started on port 8546")
        
        print("")
        print("="*60)
        print("NODE IS RUNNING")
        print("="*60)
        print("")
        print("  JSON-RPC: http://localhost:8080/v1")
        print("  WebSocket: ws://localhost:8546")
        print("  Chain ID: 1337")
        print("")
        print("="*60)
        print("Mining blocks every 15 seconds...")
        print("Press Ctrl+C to stop")
        print("="*60)
        print("")
        
        # Mining loop
        try:
            while self.running:
                time.sleep(15)
                self.mine_block()
        except KeyboardInterrupt:
            print("")
            print("Shutting down...")
            self.running = False

def main():
    node = FullNode()
    node.run()

if __name__ == "__main__":
    main()
'@

Set-Content -Path "main.py" -Value $fixedMain -Encoding UTF8
Write-Host "   [OK] main.py fixed" -ForegroundColor Green

# ============================================================
# 3. ИСПРАВЛЕНИЕ run_node.bat
# ============================================================
Write-Host ""
Write-Host "[3/4] Fixing run_node.bat..." -ForegroundColor Yellow

$fixedRun = @'
@echo off
title Absolute Blockchain Node
cd /d "C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate"
echo Starting Absolute Blockchain Node...
echo.
python -m main
pause
'@

[System.IO.File]::WriteAllText("$ProjectPath\run_node.bat", $fixedRun, [System.Text.ASCIIEncoding]::new())
Write-Host "   [OK] run_node.bat fixed" -ForegroundColor Green

# ============================================================
# 4. ПРОВЕРКА ВСЕХ НЕОБХОДИМЫХ МОДУЛЕЙ
# ============================================================
Write-Host ""
Write-Host "[4/4] Verifying all modules..." -ForegroundColor Yellow

$requiredModules = @(
    "crypto/crypto.py",
    "core/state/state_db.py",
    "core/execution/transaction.py",
    "core/execution/engine.py",
    "core/blockchain/block.py",
    "core/consensus/consensus.py",
    "network/p2p/p2p.py",
    "rpc/rpc_server.py"
)

$allOk = $true
foreach ($module in $requiredModules) {
    if (Test-Path $module) {
        Write-Host "   [OK] $module" -ForegroundColor Green
    } else {
        Write-Host "   [MISSING] $module" -ForegroundColor Red
        $allOk = $false
    }
}

# ============================================================
# 5. ТЕСТОВЫЙ ЗАПУСК
# ============================================================
Write-Host ""
if ($allOk) {
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "ALL MODULES READY! STARTING NODE..." -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    
    # Run the node
    python -m main
} else {
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "SOME MODULES ARE MISSING!" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Run build_real_client.ps1 first, then this script again." -ForegroundColor Yellow
}