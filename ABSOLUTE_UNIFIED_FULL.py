#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ABSOLUTE BLOCKCHAIN ULTIMATE - FULL EDITION v54
Содержит: Blockchain + Mini-EVM + NFT + Sharding + Oracles + Telegram + P2P
"""

import json
import sqlite3
import hashlib
import time
import threading
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from contextlib import contextmanager

# ============================================================
# ИМПОРТ ВСЕХ КОМПОНЕНТОВ
# ============================================================

# NFT Marketplace
try:
    from nft_core import nft_marketplace, NFTMarketplace
    print("✅ NFT Marketplace loaded")
except ImportError as e:
    print(f"⚠️ NFT Marketplace: {e}")
    nft_marketplace = None

# Sharding
try:
    from dynamic_sharding import sharding_manager, ShardingManager
    print("✅ Sharding loaded")
except ImportError as e:
    print(f"⚠️ Sharding: {e}")
    sharding_manager = None

# Oracles
try:
    from real_world_oracles import oracles, RealWorldOracles
    print("✅ Oracles loaded")
except ImportError as e:
    print(f"⚠️ Oracles: {e}")
    oracles = None

# Telegram Bot
try:
    from telegram_super_bot import telegram_bot, TelegramBot
    print("✅ Telegram Bot loaded")
except ImportError as e:
    print(f"⚠️ Telegram Bot: {e}")
    telegram_bot = None

# P2P Network
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from network.p2p.peer_manager import peer_manager
    print("✅ P2P Network loaded")
except ImportError as e:
    print(f"⚠️ P2P Network: {e}")
    peer_manager = None

# ============================================================
# MINI-EVM (SMART CONTRACT VM)
# ============================================================

class MiniVM:
    GAS_COSTS = {"PUSH":2,"POP":2,"ADD":3,"SUB":3,"MUL":5,"DIV":5,"STORE":20,"LOAD":20,"STOP":0,"INC":2,"DEC":2,"EQ":3,"LT":3,"GT":3,"JUMP":1,"JUMPI":1}
    def __init__(self, gas_limit=10000):
        self.stack=[]; self.storage={}; self.gas_used=0; self.gas_limit=gas_limit; self.pc=0; self.running=True
    def _consume_gas(self,op):
        cost=self.GAS_COSTS.get(op,1)
        if self.gas_used+cost>self.gas_limit: raise Exception(f"Out of gas")
        self.gas_used+=cost
    def execute(self,bytecode):
        self.pc=0; self.gas_used=0; self.stack=[]; self.storage={}; self.running=True
        while self.pc<len(bytecode) and self.running:
            op,arg=bytecode[self.pc]; self._consume_gas(op)
            if op=="PUSH": self.stack.append(arg)
            elif op=="POP": self.stack.pop()
            elif op=="ADD": b=self.stack.pop(); a=self.stack.pop(); self.stack.append(a+b)
            elif op=="SUB": b=self.stack.pop(); a=self.stack.pop(); self.stack.append(a-b)
            elif op=="MUL": b=self.stack.pop(); a=self.stack.pop(); self.stack.append(a*b)
            elif op=="DIV": b=self.stack.pop(); a=self.stack.pop(); self.stack.append(a//b if b!=0 else 0)
            elif op=="STORE": key=self.stack.pop(); val=self.stack.pop(); self.storage[key]=val
            elif op=="LOAD": key=self.stack.pop(); self.stack.append(self.storage.get(key,0))
            elif op=="INC": 
                if not self.stack: self.stack.append(0)
                self.stack[-1]+=1
            elif op=="DEC": 
                if not self.stack: self.stack.append(0)
                self.stack[-1]-=1
            elif op=="EQ": b=self.stack.pop(); a=self.stack.pop(); self.stack.append(1 if a==b else 0)
            elif op=="LT": b=self.stack.pop(); a=self.stack.pop(); self.stack.append(1 if a<b else 0)
            elif op=="GT": b=self.stack.pop(); a=self.stack.pop(); self.stack.append(1 if a>b else 0)
            elif op=="STOP": self.running=False; break
            self.pc+=1
        return {"stack":self.stack.copy(),"storage":self.storage.copy(),"gas_used":self.gas_used,"success":self.gas_used<=self.gas_limit}
    def reset(self): self.stack=[]; self.storage={}; self.gas_used=0; self.pc=0

class ContractManager:
    def __init__(self): self.contracts={}; self.vm=MiniVM()
    def deploy(self,bytecode,address):
        if address in self.contracts: return False
        self.contracts[address]={"bytecode":bytecode,"storage":{},"deployed_at":time.time()}
        return True
    def call(self,address,func,args):
        if address not in self.contracts: return None
        contract=self.contracts[address]; self.vm.reset()
        bytecode=contract["bytecode"].copy()
        for arg in reversed(args): bytecode.insert(0,("PUSH",arg))
        bytecode.append(("STOP",None))
        result=self.vm.execute(bytecode)
        contract["storage"]=self.vm.storage.copy()
        return {"success":result["success"],"gas_used":result["gas_used"],"stack":result["stack"]}
    def get_contracts(self): return self.contracts

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================
@dataclass
class Config:
    VERSION: str = "54.0"
    NETWORK_NAME: str = "AbsoluteBlockchain"
    API_PORT: int = 8080
    BLOCK_TIME: int = 15
    BLOCK_REWARD: float = 50.0
    RATE_LIMIT_REQUESTS: int = 100

config = Config()

# ============================================================
# RATE LIMITER
# ============================================================
class RateLimiter:
    def __init__(self, rpm=100):
        self.rpm=rpm; self.tokens={}; self.last_refill={}; self.lock=threading.RLock()
    def _refill(self,key):
        now=time.time(); last=self.last_refill.get(key,now); passed=now-last; refill=passed/60.0*self.rpm
        current=self.tokens.get(key,self.rpm); self.tokens[key]=min(self.rpm,current+refill); self.last_refill[key]=now
    def allow(self,key):
        with self.lock:
            self._refill(key)
            if self.tokens.get(key,self.rpm)>=1:
                self.tokens[key]-=1; return True, int(self.tokens[key])
            return False,0
rate_limiter=RateLimiter()

# ============================================================
# MEMPOOL
# ============================================================
@dataclass
class MempoolTx:
    tx_hash:str; from_addr:str; to_addr:str; amount:float; fee:float; timestamp:float
class Mempool:
    def __init__(self): self.txs={}; self.lock=threading.RLock()
    def add(self,tx):
        with self.lock:
            if tx.tx_hash in self.txs: return False
            self.txs[tx.tx_hash]=tx; return True
    def get_pending(self,limit=100): 
        with self.lock: return sorted(self.txs.values(),key=lambda t:t.fee,reverse=True)[:limit]
    def remove(self,hash): 
        with self.lock: return self.txs.pop(hash,None) is not None
    def size(self): return len(self.txs)
mempool=Mempool()

# ============================================================
# STATE MANAGER
# ============================================================
class StateManager:
    def __init__(self): self.balances={}; self.lock=threading.RLock()
    def get(self,addr): return self.balances.get(addr,0)
    def set(self,addr,amt): self.balances[addr]=amt
    def transfer(self,fr,to,amt):
        with self.lock:
            if self.balances.get(fr,0)<amt: return False
            self.balances[fr]-=amt; self.balances[to]=self.balances.get(to,0)+amt; return True
state_manager=StateManager()

# ============================================================
# БЛОКЧЕЙН ЯДРО
# ============================================================
class Block:
    def __init__(self,height,prev_hash,miner):
        self.height=height; self.prev_hash=prev_hash; self.timestamp=int(time.time())
        self.miner=miner; self.txs=[]; self.nonce=0; self.hash=self.calc_hash()
    def calc_hash(self):
        data=f"{self.height}{self.prev_hash}{self.timestamp}{self.miner}{json.dumps(self.txs)}{self.nonce}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    def to_dict(self):
        return {"height":self.height,"block_hash":self.hash,"previous_hash":self.prev_hash,
                "timestamp":self.timestamp,"miner":self.miner,"transactions":self.txs,"transaction_count":len(self.txs)}

class Transaction:
    def __init__(self,fr,to,amt):
        self.fr=fr; self.to=to; self.amt=amt; self.ts=int(time.time())
        self.hash=hashlib.sha256(f"{fr}{to}{amt}{self.ts}".encode()).hexdigest()[:16]

class Blockchain:
    def __init__(self):
        self.chain=[]; self.contract_manager=ContractManager()
        if telegram_bot: telegram_bot.set_blockchain(self)
        self._load_or_create()
    def _load_or_create(self):
        os.makedirs("data",exist_ok=True); chain_file="data/chain.json"
        if os.path.exists(chain_file):
            try:
                with open(chain_file) as f:
                    for d in json.load(f):
                        b=Block(d['height'],d['previous_hash'],d['miner'])
                        b.hash=d['block_hash']; b.timestamp=d['timestamp']; b.txs=d.get('transactions',[])
                        self.chain.append(b)
                print(f"📦 Loaded {len(self.chain)} blocks")
            except: self._create_genesis()
        else: self._create_genesis()
        state_manager.set(self.get_wallet(),1000000)
    def _create_genesis(self):
        g=Block(0,"0"*64,"genesis"); g.hash=g.calc_hash(); self.chain.append(g); self._save()
        print("🌱 Genesis created")
    def _save(self):
        with open("data/chain.json","w") as f: json.dump([b.to_dict() for b in self.chain],f,indent=2)
    def get_wallet(self):
        wf="data/wallet.json"
        if os.path.exists(wf):
            try:
                with open(wf) as f: return json.load(f).get('address','0x94f45b97f9bc27')
            except: pass
        return '0x94f45b97f9bc27'
    def get_balance(self,addr): return state_manager.get(addr)
    def add_tx(self,tx):
        if state_manager.get(tx.fr)<tx.amt+0.001: return False
        return mempool.add(MempoolTx(tx.hash,tx.fr,tx.to,tx.amt,0.001,tx.ts))
    def mine(self,miner=None):
        if not miner: miner=self.get_wallet()
        pending=mempool.get_pending(50)
        b=Block(len(self.chain),self.chain[-1].hash,miner)
        for tx in pending[:20]:
            if state_manager.transfer(tx.from_addr,tx.to_addr,tx.amount):
                b.txs.append({"tx_hash":tx.tx_hash,"from":tx.from_addr,"to":tx.to_addr,"amount":tx.amount})
                mempool.remove(tx.tx_hash)
        state_manager.set(miner,state_manager.get(miner)+config.BLOCK_REWARD)
        b.hash=b.calc_hash()
        self.chain.append(b); self._save()
        print(f"📦 Block #{b.height}: {b.hash} | {len(b.txs)} txs")
        return b
    def get_info(self):
        return {"chain":config.NETWORK_NAME,"blocks":len(self.chain)-1,"mining_reward":config.BLOCK_REWARD,
                "mempool_size":mempool.size(),"version":config.VERSION,"vm_supported":True,
                "contracts":len(self.contract_manager.get_contracts())}
    def deploy_contract(self,bytecode,owner):
        addr=hashlib.sha256(f"{owner}{time.time()}".encode()).hexdigest()[:20]
        addr="0x"+addr
        return addr if self.contract_manager.deploy(bytecode,addr) else None

# ============================================================
# API СЕРВЕР
# ============================================================
class Handler(BaseHTTPRequestHandler):
    blockchain=None
    def log_message(self,*args): pass
    def do_GET(self):
        p=urlparse(self.path).path
        if not Handler.blockchain: Handler.blockchain=blockchain
        allowed,_=rate_limiter.allow(self.client_address[0])
        if not allowed: return self._json({"error":"Rate limit"},429)
        if p=="/" or p=="/index.html": self._html(self._web())
        elif p=="/explorer": self._html(self._explorer())
        elif p=="/api/stats": self._json(Handler.blockchain.get_info())
        elif p=="/api/blocks": self._json({"blocks":[b.to_dict() for b in Handler.blockchain.chain[1:]]})
        elif p=="/api/balance":
            q=parse_qs(urlparse(self.path).query); addr=q.get('address',[''])[0]
            if addr: self._json({"address":addr,"balance":Handler.blockchain.get_balance(addr)})
            else: self._json({"error":"Address required"},400)
        elif p=="/api/nft":
            if nft_marketplace: self._json(nft_marketplace.get_all_tokens())
            else: self._json({"error":"NFT not available"},503)
        elif p=="/api/prices":
            if oracles: self._json(oracles.get_all_prices())
            else: self._json({"error":"Oracles not available"},503)
        elif p=="/api/sharding":
            if sharding_manager: self._json(sharding_manager.get_all_stats())
            else: self._json({"error":"Sharding not available"},503)
        else: self._json({"error":"Not found"},404)
    def do_POST(self):
        length=int(self.headers.get('Content-Length',0))
        body=self.rfile.read(length) if length else b'{}'
        try: data=json.loads(body.decode())
        except: data={}
        p=self.path
        if p=="/api/transaction/send":
            tx=Transaction(data.get('from'),data.get('to'),float(data.get('amount',0)))
            ok=Handler.blockchain.add_tx(tx)
            self._json({"success":ok,"tx_hash":tx.hash if ok else None})
        elif p=="/api/mine":
            b=Handler.blockchain.mine(data.get('miner'))
            self._json({"success":b is not None,"height":b.height if b else 0})
        elif p=="/api/contract/deploy":
            addr=Handler.blockchain.deploy_contract(data.get('bytecode',[]),data.get('owner',Handler.blockchain.get_wallet()))
            self._json({"success":addr is not None,"address":addr})
        elif p=="/api/nft/mint":
            if nft_marketplace:
                ok=nft_marketplace.mint(data['token_id'],data['name'],data.get('description',''),data.get('image',''),data.get('creator'),float(data.get('price',0)))
                self._json({"success":ok})
            else: self._json({"error":"NFT not available"},503)
        else: self._json({"error":"Not found"},404)
    def _json(self,d,status=200): self.send_response(status); self.send_header('Content-Type','application/json'); self.end_headers(); self.wfile.write(json.dumps(d).encode())
    def _html(self,h): self.send_response(200); self.send_header('Content-Type','text/html'); self.end_headers(); self.wfile.write(h.encode())
    def _web(self):
        return '<!DOCTYPE html><html><head><title>Absolute Blockchain Ultimate</title><style>body{background:#0a0a0a;color:#0f0;font-family:monospace;padding:20px}</style></head><body><h1>🔗 Absolute Blockchain Ultimate v54</h1><div id="stats"></div><h2>💰 Send Transaction</h2><input id="to" placeholder="0x..."><input id="amt" placeholder="Amount"><button onclick="send()">Send</button><div id="result"></div><script>async function send(){const r=await fetch("/api/transaction/send",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({from:"0x94f45b97f9bc27",to:document.getElementById("to").value,amount:parseFloat(document.getElementById("amt").value)})});const d=await r.json();document.getElementById("result").innerHTML=d.success?"✅ Tx sent: "+d.tx_hash:"❌ Failed";loadStats()}async function loadStats(){const r=await fetch("/api/stats");const d=await r.json();document.getElementById("stats").innerHTML=`<div>📦 Blocks: ${d.blocks}</div><div>📋 Mempool: ${d.mempool_size}</div><div>📄 Contracts: ${d.contracts}</div><div>⚡ Version: ${d.version}</div>`}loadStats();setInterval(loadStats,3000);</script></body></html>'
    def _explorer(self):
        return '<!DOCTYPE html><html><head><title>Explorer</title><style>body{background:#0a0a0a;color:#0f0;font-family:monospace;padding:20px}.block{border:1px solid #0f0;margin:10px 0;padding:10px}</style></head><body><h1>🔍 Explorer</h1><button onclick="load()">Refresh</button><div id="blocks"></div><script>async function load(){const r=await fetch("/api/blocks");const d=await r.json();let html="";for(const b of d.blocks.reverse()){html+=`<div class="block"><b>Block #${b.height}</b><div>Hash: ${b.block_hash}</div><div>Miner: ${b.miner.substring(0,20)}...</div><div>📝 Txs: ${b.transaction_count}</div></div>`}document.getElementById("blocks").innerHTML=html||"<p>No blocks</p>"}load();setInterval(load,5000);</script></body></html>'

# ============================================================
# ЗАПУСК
# ============================================================
def main():
    print("="*60)
    print("ABSOLUTE BLOCKCHAIN ULTIMATE - FULL EDITION v54")
    print("="*60)
    global blockchain
    blockchain = Blockchain()
    Handler.blockchain = blockchain
    
    # Запуск P2P
    if peer_manager:
        try:
            peer_manager.start()
        except: pass
    
    # Запуск Telegram бота (в отдельном потоке)
    if telegram_bot:
        print("🤖 Telegram Bot: use /help in @YourBot")
    
    server = HTTPServer(('0.0.0.0', config.API_PORT), Handler)
    print(f"🌐 Web: http://localhost:{config.API_PORT}")
    print(f"🔍 Explorer: http://localhost:{config.API_PORT}/explorer")
    print(f"📡 API: http://localhost:{config.API_PORT}/api/stats")
    print(f"🎨 NFT: {len(nft_marketplace.get_all_tokens()) if nft_marketplace else 0} tokens")
    print(f"🔷 Sharding: {sharding_manager.num_shards if sharding_manager else 0} shards")
    print(f"💰 Oracles: {'OK' if oracles else 'No'}")
    print(f"⛏️ Auto-mining every {config.BLOCK_TIME}s")
    print("="*60)
    print("🚀 Node running! Press Ctrl+C to stop")
    
    def auto_mine():
        while True:
            time.sleep(config.BLOCK_TIME)
            try: blockchain.mine()
            except: pass
    threading.Thread(target=auto_mine, daemon=True).start()
    
    try: server.serve_forever()
    except KeyboardInterrupt: 
        print("\n⏹️ Shutting down...")
        if peer_manager: peer_manager.stop()
        server.shutdown()

if __name__ == '__main__':
    blockchain = None
    main()
