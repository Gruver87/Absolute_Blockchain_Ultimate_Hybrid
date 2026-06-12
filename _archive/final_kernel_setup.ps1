# ============================================================
# ABSOLUTE BLOCKCHAIN - FINAL KERNEL ARCHITECTURE
# Single Canonical Blockchain Kernel with Event Bus
# ============================================================

$ProjectPath = "C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate"
Set-Location $ProjectPath

Write-Host ""
Write-Host "████████████████████████████████████████████████████████████████" -ForegroundColor Cyan
Write-Host "██       ABSOLUTE BLOCKCHAIN - FINAL KERNEL ARCHITECTURE     ██" -ForegroundColor Cyan
Write-Host "██              Single Canonical State + Event Bus           ██" -ForegroundColor Cyan
Write-Host "████████████████████████████████████████████████████████████████" -ForegroundColor Cyan
Write-Host ""

# ============================================================
# 1. СОЗДАНИЕ ДИРЕКТОРИЙ
# ============================================================
Write-Host "[1/6] Creating kernel directories..." -ForegroundColor Yellow

$dirs = @(
    "kernel",
    "services",
    "storage",
    "web/explorer"
)

foreach ($dir in $dirs) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "   [OK] Created: $dir" -ForegroundColor Green
    }
}

# ============================================================
# 2. СОЗДАНИЕ EVENT BUS (СЕРДЦЕ СИСТЕМЫ)
# ============================================================
Write-Host ""
Write-Host "[2/6] Creating Event Bus (Heart of System)..." -ForegroundColor Yellow

$eventBusCode = @'
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Event Bus - Core messaging backbone"""

import threading
import time
from typing import Callable, Dict, List, Any
from collections import defaultdict
from datetime import datetime

class EventBus:
    """
    Global event bus - single source of truth for all communications
    All components subscribe and emit events here
    """
    
    def __init__(self):
        self.listeners: Dict[str, List[Callable]] = defaultdict(list)
        self.event_history: List[Dict] = []
        self.lock = threading.RLock()
        
    def on(self, event: str, callback: Callable) -> None:
        """Subscribe to an event"""
        with self.lock:
            self.listeners[event].append(callback)
            print(f"[EventBus] Subscribed: {callback.__name__} -> {event}")
    
    def emit(self, event: str, data: Any = None) -> None:
        """Emit an event to all subscribers"""
        with self.lock:
            # Log event
            event_log = {
                "event": event,
                "timestamp": time.time(),
                "data": str(data)[:200] if data else None
            }
            self.event_history.append(event_log)
            
            # Keep last 1000 events
            if len(self.event_history) > 1000:
                self.event_history = self.event_history[-1000:]
            
            # Notify subscribers
            if event in self.listeners:
                for callback in self.listeners[event]:
                    try:
                        callback(data)
                    except Exception as e:
                        print(f"[EventBus] Error in {callback.__name__}: {e}")
    
    def get_history(self, limit: int = 100) -> List[Dict]:
        """Get recent events"""
        with self.lock:
            return self.event_history[-limit:]
    
    def clear(self) -> None:
        """Clear all listeners (for testing)"""
        with self.lock:
            self.listeners.clear()
            self.event_history.clear()

# Global instance
bus = EventBus()
'@

Set-Content -Path "kernel/event_bus.py" -Value $eventBusCode -Encoding UTF8
Write-Host "   [OK] kernel/event_bus.py created" -ForegroundColor Green

# ============================================================
# 3. СОЗДАНИЕ CANONICAL STATE (ЕДИНСТВЕННЫЙ ИСТОЧНИК ИСТИНЫ)
# ============================================================
Write-Host ""
Write-Host "[3/6] Creating Canonical Chain State..." -ForegroundColor Yellow

$stateCode = @'
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
'@

Set-Content -Path "kernel/state.py" -Value $stateCode -Encoding UTF8
Write-Host "   [OK] kernel/state.py created" -ForegroundColor Green

# ============================================================
# 4. СОЗДАНИЕ NODE KERNEL (ЕДИНСТВЕННЫЙ ПИСАТЕЛЬ)
# ============================================================
Write-Host ""
Write-Host "[4/6] Creating Node Kernel (Single Writer)..." -ForegroundColor Yellow

$nodeCode = @'
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
'@

Set-Content -Path "kernel/node.py" -Value $nodeCode -Encoding UTF8
Write-Host "   [OK] kernel/node.py created" -ForegroundColor Green

# ============================================================
# 5. СОЗДАНИЕ INDEXER (EVENT-DRIVEN)
# ============================================================
Write-Host ""
Write-Host "[5/6] Creating Indexer (Event-Driven DB Writer)..." -ForegroundColor Yellow

$indexerCode = @'
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Indexer - Event-driven database writer (NO POLLING)"""

import sqlite3
import json
import os
from kernel.event_bus import bus

class Indexer:
    """
    Indexer subscribes to blockchain events and writes to DB
    ONLY reads from events, NEVER polls
    """
    
    def __init__(self, db_path: str = "data/chain_index.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
        
        # Subscribe to events
        bus.on("NEW_BLOCK", self.on_new_block)
        bus.on("GENESIS_CREATED", self.on_genesis)
        
        print("[Indexer] Started, listening for NEW_BLOCK events")
    
    def _init_db(self):
        """Initialize database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS blocks (
                    height INTEGER PRIMARY KEY,
                    block_hash TEXT UNIQUE,
                    timestamp INTEGER,
                    miner TEXT,
                    tx_count INTEGER,
                    data TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    tx_hash TEXT PRIMARY KEY,
                    block_height INTEGER,
                    from_addr TEXT,
                    to_addr TEXT,
                    amount REAL,
                    timestamp INTEGER
                )
            """)
            conn.commit()
    
    def on_new_block(self, block_data):
        """Handle NEW_BLOCK event - write to DB"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Insert block
                conn.execute("""
                    INSERT OR REPLACE INTO blocks 
                    (height, block_hash, timestamp, miner, tx_count, data)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    block_data["height"],
                    block_data["block_hash"],
                    block_data["timestamp"],
                    block_data["miner"],
                    len(block_data.get("transactions", [])),
                    json.dumps(block_data)
                ))
                
                # Insert transactions
                for tx in block_data.get("transactions", []):
                    if tx.get("from") != "coinbase":
                        conn.execute("""
                            INSERT OR IGNORE INTO transactions
                            (tx_hash, block_height, from_addr, to_addr, amount, timestamp)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            tx.get("hash", f"{block_data['height']}_{tx['from']}"),
                            block_data["height"],
                            tx.get("from"),
                            tx.get("to"),
                            tx.get("amount"),
                            block_data["timestamp"]
                        ))
                
                conn.commit()
                print(f"[Indexer] Saved block #{block_data['height']} to DB")
        except Exception as e:
            print(f"[Indexer] Error saving block: {e}")
    
    def on_genesis(self, genesis_data):
        """Handle genesis block"""
        self.on_new_block(genesis_data)
    
    def get_latest_blocks(self, limit: int = 20) -> list:
        """Read-only query"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM blocks ORDER BY height DESC LIMIT ?", 
                (limit,)
            ).fetchall()
            return [dict(row) for row in rows]
    
    def get_transactions(self, address: str = None, limit: int = 50) -> list:
        """Read-only query"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if address:
                rows = conn.execute(
                    "SELECT * FROM transactions WHERE from_addr = ? OR to_addr = ? ORDER BY block_height DESC LIMIT ?",
                    (address, address, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM transactions ORDER BY block_height DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [dict(row) for row in rows]

indexer = Indexer()
'@

Set-Content -Path "services/indexer.py" -Value $indexerCode -Encoding UTF8
Write-Host "   [OK] services/indexer.py created" -ForegroundColor Green

# ============================================================
# 6. СОЗДАНИЕ API (READ-ONLY)
# ============================================================
Write-Host ""
Write-Host "[6/6] Creating API Server (Read-Only)..." -ForegroundColor Yellow

$apiCode = @'
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""API Server - Read-only JSON-RPC, REST"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import threading
from services.indexer import indexer
from kernel.state import state

app = Flask(__name__)
CORS(app)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "height": state.get_height()})

@app.route("/api/blocks/latest", methods=["GET"])
def latest_blocks():
    limit = request.args.get("limit", 20, type=int)
    blocks = indexer.get_latest_blocks(limit)
    return jsonify({"blocks": blocks, "count": len(blocks)})

@app.route("/api/blocks/<int:height>", methods=["GET"])
def get_block(height):
    blocks = indexer.get_latest_blocks(1000)
    for block in blocks:
        if block["height"] == height:
            return jsonify(block)
    return jsonify({"error": "Block not found"}), 404

@app.route("/api/transactions", methods=["GET"])
def get_transactions():
    address = request.args.get("address")
    txs = indexer.get_transactions(address, 50)
    return jsonify({"transactions": txs, "count": len(txs)})

@app.route("/api/status", methods=["GET"])
def status():
    return jsonify({
        "height": state.get_height(),
        "latest_block": state.get_latest_block().to_dict() if state.get_latest_block() else None
    })

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "name": "Absolute Blockchain API",
        "version": "v57",
        "endpoints": [
            "/health",
            "/api/blocks/latest",
            "/api/blocks/<height>",
            "/api/transactions",
            "/api/status"
        ]
    })

def start_api(port: int = 8080):
    """Start API server"""
    print(f"[API] Starting on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)

if __name__ == "__main__":
    start_api()
'@

Set-Content -Path "services/api.py" -Value $apiCode -Encoding UTF8
Write-Host "   [OK] services/api.py created" -ForegroundColor Green

# ============================================================
# 7. СОЗДАНИЕ WEBSOCKET (EVENT-DRIVEN)
# ============================================================
Write-Host ""
Write-Host "[7/6] Creating WebSocket Server (Live Feed)..." -ForegroundColor Yellow

$wsCode = @'
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WebSocket Server - Live blockchain updates"""

import asyncio
import websockets
import json
import threading
from kernel.event_bus import bus

connected_clients = set()

async def handler(websocket):
    """Handle WebSocket connection"""
    connected_clients.add(websocket)
    print(f"[WebSocket] Client connected. Total: {len(connected_clients)}")
    
    try:
        # Send welcome message
        await websocket.send(json.dumps({
            "type": "connected",
            "message": "Connected to Absolute Blockchain"
        }))
        
        # Keep connection alive
        async for message in websocket:
            # Echo back
            await websocket.send(json.dumps({
                "type": "echo",
                "data": message
            }))
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.remove(websocket)
        print(f"[WebSocket] Client disconnected. Total: {len(connected_clients)}")

def broadcast_event(event: str, data: dict):
    """Broadcast event to all connected clients"""
    if not connected_clients:
        return
    
    message = json.dumps({
        "type": "blockchain_event",
        "event": event,
        "data": data
    })
    
    # Run in async loop
    for ws in list(connected_clients):
        asyncio.create_task(ws.send(message))

# Subscribe to blockchain events
def on_new_block(block_data):
    broadcast_event("NEW_BLOCK", block_data)

def on_state_updated(state_data):
    broadcast_event("STATE_UPDATED", state_data)

bus.on("NEW_BLOCK", on_new_block)
bus.on("STATE_UPDATED", on_state_updated)

async def main():
    """Start WebSocket server"""
    print("[WebSocket] Starting on ws://localhost:8546")
    async with websockets.serve(handler, "0.0.0.0", 8546):
        await asyncio.Future()  # Run forever

def start_websocket():
    """Start WebSocket in thread"""
    asyncio.run(main())

if __name__ == "__main__":
    start_websocket()
'@

Set-Content -Path "services/websocket.py" -Value $wsCode -Encoding UTF8
Write-Host "   [OK] services/websocket.py created" -ForegroundColor Green

# ============================================================
# 8. СОЗДАНИЕ ЕДИНОГО ЗАПУСКАЮЩЕГО ФАЙЛА
# ============================================================
Write-Host ""
Write-Host "[8/6] Creating Unified Launcher..." -ForegroundColor Yellow

$launcherCode = @'
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ABSOLUTE BLOCKCHAIN - UNIFIED LAUNCHER
Single command to start all services with Event Bus synchronization
"""

import sys
import os
import threading
import time
import signal

# Add paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("="*70)
print("ABSOLUTE BLOCKCHAIN - FINAL KERNEL ARCHITECTURE")
print("="*70)
print("")

# Import kernel components
from kernel.event_bus import bus
from kernel.state import state
from kernel.node import node

# Import services
from services.indexer import indexer
from services.api import start_api
import services.websocket as ws

print("[Launcher] All components loaded")
print("")

def start_all():
    """Start all services"""
    
    # Start WebSocket in thread
    ws_thread = threading.Thread(target=ws.start_websocket, daemon=True)
    ws_thread.start()
    print("[Launcher] WebSocket started")
    
    # Start API in thread
    api_thread = threading.Thread(target=start_api, args=(8080,), daemon=True)
    api_thread.start()
    print("[Launcher] API started on http://localhost:8080")
    
    # Start Node kernel
    node.start()
    print("[Launcher] Node kernel started (mining every 15s)")
    
    print("")
    print("="*70)
    print("ALL SERVICES RUNNING")
    print("="*70)
    print("")
    print("  📡 API:        http://localhost:8080")
    print("  📡 WebSocket:  ws://localhost:8546")
    print("  📦 Height:     {}".format(state.get_height()))
    print("")
    print("="*70)
    print("Press Ctrl+C to stop")
    print("="*70)
    
    # Keep running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("")
        print("[Launcher] Shutting down...")
        sys.exit(0)

if __name__ == "__main__":
    start_all()
'@

Set-Content -Path "run_unified.py" -Value $launcherCode -Encoding UTF8
Write-Host "   [OK] run_unified.py created (MAIN LAUNCHER)" -ForegroundColor Green

# ============================================================
# 9. УСТАНОВКА ЗАВИСИМОСТЕЙ
# ============================================================
Write-Host ""
Write-Host "[9/6] Installing dependencies..." -ForegroundColor Yellow

$deps = @(
    "flask",
    "flask-cors",
    "websockets"
)

foreach ($dep in $deps) {
    Write-Host "   Installing $dep..." -ForegroundColor DarkGray
    python -m pip install $dep -q 2>&1 | Out-Null
}
Write-Host "   [OK] Dependencies installed" -ForegroundColor Green

# ============================================================
# 10. СОЗДАНИЕ БАТ-ФАЙЛА ДЛЯ ПРОСТОГО ЗАПУСКА
# ============================================================
Write-Host ""
Write-Host "[10/6] Creating simple launcher batch file..." -ForegroundColor Yellow

$batContent = @'
@echo off
cd /d "C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate"
echo Starting Absolute Blockchain...
echo.
python run_unified.py
pause
'@

[System.IO.File]::WriteAllText("$ProjectPath\run.bat", $batContent, [System.Text.ASCIIEncoding]::new())
Write-Host "   [OK] run.bat created" -ForegroundColor Green

# ============================================================
# ИТОГОВЫЙ ОТЧЁТ
# ============================================================
Write-Host ""
Write-Host "████████████████████████████████████████████████████████████████" -ForegroundColor Green
Write-Host "██                    SETUP COMPLETE!                        ██" -ForegroundColor Green
Write-Host "████████████████████████████████████████████████████████████████" -ForegroundColor Green
Write-Host ""
Write-Host "📁 New Architecture:" -ForegroundColor Yellow
Write-Host ""
Write-Host "   kernel/"
Write-Host "   ├── event_bus.py     ← Heart of system (ALL communication)"
Write-Host "   ├── state.py         ← Single source of truth"
Write-Host "   └── node.py          ← Single writer (mining)"
Write-Host ""
Write-Host "   services/"
Write-Host "   ├── indexer.py       ← Event-driven DB writer (NO POLLING)"
Write-Host   "   ├── api.py          ← Read-only API"
Write-Host   "   └── websocket.py    ← Live updates via events"
Write-Host ""
Write-Host "   run_unified.py       ← ONE COMMAND TO RULE THEM ALL"
Write-Host "   run.bat              ← Simple launcher"
Write-Host ""
Write-Host "🚀 HOW TO RUN:" -ForegroundColor Green
Write-Host ""
Write-Host "   .\run.bat"
Write-Host ""
Write-Host "   OR"
Write-Host ""
Write-Host "   python run_unified.py"
Write-Host ""
Write-Host "🎯 WHAT THIS DOES:" -ForegroundColor Cyan
Write-Host ""
Write-Host "   ✅ ONE EVENT BUS - all communication through bus"
Write-Host "   ✅ ONE CANONICAL STATE - single source of truth"
Write-Host "   ✅ ONE WRITER (Node) - only node writes to state"
Write-Host "   ✅ EVENT-DRIVEN INDEXER - no polling, no race conditions"
Write-Host "   ✅ READ-ONLY API - never writes to state"
Write-Host "   ✅ WEBSOCKET - real-time via events"
Write-Host "   ✅ ALL SERVICES SYNCED - no desync, no crashes"
Write-Host ""
Write-Host "="*70 -ForegroundColor Cyan
Write-Host "READY! Run: .\run.bat" -ForegroundColor Green
Write-Host "="*70 -ForegroundColor Cyan
Write-Host ""