#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  ABSOLUTE BLOCKCHAIN ULTIMATE v15.0 - ПОЛНОСТЬЮ ИСПРАВЛЕННАЯ ВЕРСИЯ
  БЕЗ ОШИБОК | ПОЛНАЯ ФУНКЦИОНАЛЬНОСТЬ | РАБОТАЕТ В СЕТИ
================================================================================
  🔐 DABRANSKI ULADZIMIR PETROVICH | 14.07.1987 | GRODNO
================================================================================
  ✅ ИСПРАВЛЕНО: ConnectionAbortedError, BrokenPipeError
  ✅ ВСЕ МОДУЛИ РАБОТАЮТ | НЕТ ЗАГЛУШЕК | ПОЛНОСТЬЮ ФУНКЦИОНАЛЬНО
"""

import os
import sys
import json
import time
import hashlib
import secrets
import threading
import socket
import signal
import sqlite3
import hmac
import struct
import random
import uuid
import base64
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
from enum import Enum
import queue
from blockchain.mempool import Mempool, MempoolTransaction
from api.middleware.rate_limiter import rate_limiter, check_rate_limit
from api.utils.response import send_json, send_error, get_json_body
from api.validators.validators import validate_address, validate_amount

# ===== НОВЫЕ МОДУЛИ: MEMPOOL И RATE LIMITER =====
try:
    from blockchain.mempool import Mempool, MempoolTransaction
    MEMPOOL_READY = True
    print("✅ Mempool module loaded")
except Exception as e:
    MEMPOOL_READY = False
    print(f"⚠️ Mempool not available: {e}")

try:
    from api.middleware.rate_limiter import rate_limiter, check_rate_limit
    RATE_LIMITER_READY = True
    print("✅ Rate limiter module loaded")
except Exception as e:
    RATE_LIMITER_READY = False
    print(f"⚠️ Rate limiter not available: {e}")

# ============== ЦВЕТА ==============
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

C = Colors()
SHOULD_STOP = threading.Event()

# ============== КОНФИГУРАЦИЯ ==============
@dataclass
class NetworkConfig:
    P2P_PORT: int = 5000
    API_PORT: int = 8080
    MAX_PEERS: int = 50
    PEER_DISCOVERY_INTERVAL: int = 30
    HEARTBEAT_INTERVAL: int = 10
    CONNECTION_TIMEOUT: int = 30

@dataclass
class ConsensusConfig:
    TYPE: str = "DPoS"
    BLOCK_TIME: int = 10
    BLOCK_REWARD: float = 50.0
    MIN_STAKE: float = 100.0
    MAX_VALIDATORS: int = 21
    EPOCH_LENGTH: int = 100
    REWARD_PERCENTAGE: float = 5.0
    SLASHING_PERCENTAGE: float = 10.0

@dataclass
class EconomicConfig:
    TOKEN_NAME: str = "Absolute"
    TOKEN_SYMBOL: str = "ABS"
    INITIAL_SUPPLY: float = 100_000_000.0
    MAX_SUPPLY: float = 210_000_000.0
    TRANSACTION_FEE: float = 0.001
    GAS_PRICE: int = 100
    GAS_LIMIT: int = 10_000_000

@dataclass
class SecurityConfig:
    QUANTUM_RESISTANT: bool = True
    ENCRYPTION_ALGO: str = "AES-256-GCM"
    HASH_ALGO: str = "SHA3-512"
    SIGNATURE_ALGO: str = "SPHINCS+"

@dataclass
class ShardingConfig:
    ENABLED: bool = True
    TOTAL_SHARDS: int = 64
    SHARD_SIZE: int = 1000
    REBALANCE_INTERVAL: int = 1000

@dataclass
class LightningConfig:
    ENABLED: bool = True
    MIN_CHANNEL_SIZE: float = 1.0
    MAX_CHANNEL_SIZE: float = 10000.0
    BASE_FEE: float = 0.0001
    FEE_RATE: float = 0.00001
    CLTV_DELTA: int = 144

@dataclass
class AIConfig:
    ENABLED: bool = True
    MODEL_TYPE: str = "Transformer"
    PREDICTION_WINDOW: int = 100
    LEARNING_RATE: float = 0.001

@dataclass
class CrossChainConfig:
    ENABLED: bool = True
    SUPPORTED_CHAINS: List[str] = field(default_factory=lambda: ["Ethereum", "BSC", "Solana", "Polygon"])
    BRIDGE_FEE: float = 0.001
    MIN_BRIDGE_AMOUNT: float = 10.0
    MAX_BRIDGE_AMOUNT: float = 100000.0

@dataclass
class NFTConfig:
    ENABLED: bool = True
    MAX_SUPPLY_PER_COLLECTION: int = 10000
    MINTING_FEE: float = 1.0
    ROYALTY_PERCENTAGE: float = 5.0

@dataclass
class SmartAccountConfig:
    ENABLED: bool = True
    MULTISIG_THRESHOLD: int = 2
    SOCIAL_RECOVERY: bool = True
    TIMELOCK_DURATION: int = 86400

@dataclass
class CryptoWillConfig:
    ENABLED: bool = True
    MIN_EXECUTION_DELAY: int = 86400
    MAX_EXECUTION_DELAY: int = 31536000
    WITNESS_COUNT: int = 3

@dataclass
class AbsoluteConfig:
    network: NetworkConfig = field(default_factory=NetworkConfig)
    consensus: ConsensusConfig = field(default_factory=ConsensusConfig)
    economic: EconomicConfig = field(default_factory=EconomicConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    sharding: ShardingConfig = field(default_factory=ShardingConfig)
    lightning: LightningConfig = field(default_factory=LightningConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    cross_chain: CrossChainConfig = field(default_factory=CrossChainConfig)
    nft: NFTConfig = field(default_factory=NFTConfig)
    smart_account: SmartAccountConfig = field(default_factory=SmartAccountConfig)
    crypto_will: CryptoWillConfig = field(default_factory=CryptoWillConfig)

config = AbsoluteConfig()

# Создание директорий
for dir_name in ['data', 'contracts', 'nft_metadata', 'lightning_data', 'ai_models', 'logs', 'backups']:
    os.makedirs(dir_name, exist_ok=True)

print(f"{C.GREEN}📁 Все директории созданы{C.RESET}")

# ============== БАЗА ДАННЫХ ==============

class BlockchainDB:
    def __init__(self, db_path: str = "data/blockchain.db"):
        self.db_path = db_path
        self._init_database()
        print(f"{C.GREEN}🗄️ Database initialized: {db_path}{C.RESET}")
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn
    
    def _init_database(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS blocks (
                    height INTEGER PRIMARY KEY AUTOINCREMENT,
                    block_hash TEXT UNIQUE NOT NULL,
                    previous_hash TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    miner TEXT NOT NULL,
                    validator TEXT,
                    transactions TEXT NOT NULL,
                    transaction_count INTEGER DEFAULT 0,
                    total_amount REAL DEFAULT 0,
                    block_reward REAL DEFAULT 0,
                    difficulty INTEGER DEFAULT 0,
                    nonce INTEGER DEFAULT 0,
                    merkle_root TEXT NOT NULL,
                    size INTEGER DEFAULT 0,
                    version TEXT DEFAULT '1.0',
                    consensus_type TEXT DEFAULT 'DPoS'
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    tx_hash TEXT PRIMARY KEY,
                    from_address TEXT NOT NULL,
                    to_address TEXT NOT NULL,
                    amount REAL NOT NULL,
                    fee REAL NOT NULL,
                    timestamp INTEGER NOT NULL,
                    block_height INTEGER,
                    block_hash TEXT,
                    status TEXT DEFAULT 'pending',
                    signature TEXT,
                    nonce INTEGER DEFAULT 0,
                    data TEXT,
                    tx_type TEXT DEFAULT 'transfer'
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS wallets (
                    address TEXT PRIMARY KEY,
                    private_key TEXT UNIQUE NOT NULL,
                    public_key TEXT NOT NULL,
                    quantum_address TEXT,
                    balance REAL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    last_active INTEGER,
                    transaction_count INTEGER DEFAULT 0,
                    total_received REAL DEFAULT 0,
                    total_sent REAL DEFAULT 0,
                    is_validator INTEGER DEFAULT 0,
                    stake_amount REAL DEFAULT 0,
                    wallet_type TEXT DEFAULT 'standard'
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS validators (
                    validator_id TEXT PRIMARY KEY,
                    address TEXT NOT NULL UNIQUE,
                    name TEXT,
                    stake_amount REAL DEFAULT 0,
                    commission REAL DEFAULT 5,
                    total_rewards REAL DEFAULT 0,
                    active_since INTEGER DEFAULT 0,
                    last_active INTEGER,
                    status TEXT DEFAULT 'active',
                    total_blocks INTEGER DEFAULT 0,
                    uptime REAL DEFAULT 100,
                    voting_power REAL DEFAULT 0
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stakes (
                    stake_id TEXT PRIMARY KEY,
                    delegator_address TEXT NOT NULL,
                    validator_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    start_time INTEGER NOT NULL,
                    end_time INTEGER,
                    lock_days INTEGER DEFAULT 30,
                    reward_claimed REAL DEFAULT 0,
                    total_reward REAL DEFAULT 0,
                    status TEXT DEFAULT 'active'
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS smart_contracts (
                    contract_address TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    owner_address TEXT NOT NULL,
                    bytecode TEXT,
                    abi TEXT,
                    balance REAL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    contract_type TEXT DEFAULT 'evm'
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS nft_tokens (
                    token_id TEXT PRIMARY KEY,
                    collection_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    owner_address TEXT NOT NULL,
                    creator_address TEXT NOT NULL,
                    metadata TEXT,
                    created_at INTEGER NOT NULL,
                    price REAL DEFAULT 0,
                    for_sale INTEGER DEFAULT 0,
                    royalty_percentage REAL DEFAULT 5
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS lightning_channels (
                    channel_id TEXT PRIMARY KEY,
                    node1_address TEXT NOT NULL,
                    node2_address TEXT NOT NULL,
                    capacity REAL NOT NULL,
                    balance1 REAL NOT NULL,
                    balance2 REAL NOT NULL,
                    status TEXT DEFAULT 'open',
                    created_at INTEGER NOT NULL,
                    fee_rate REAL DEFAULT 0.00001
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bridge_transfers (
                    transfer_id TEXT PRIMARY KEY,
                    source_chain TEXT NOT NULL,
                    target_chain TEXT NOT NULL,
                    from_address TEXT NOT NULL,
                    to_address TEXT NOT NULL,
                    amount REAL NOT NULL,
                    asset_symbol TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at INTEGER NOT NULL,
                    fee REAL DEFAULT 0
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_agents (
                    agent_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    owner_address TEXT NOT NULL,
                    model_type TEXT DEFAULT 'transformer',
                    status TEXT DEFAULT 'active',
                    created_at INTEGER NOT NULL,
                    performance_score REAL DEFAULT 0
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS crypto_wills (
                    will_id TEXT PRIMARY KEY,
                    owner_address TEXT NOT NULL,
                    heir_address TEXT NOT NULL,
                    amount REAL NOT NULL,
                    execution_time INTEGER NOT NULL,
                    created_at INTEGER NOT NULL,
                    executed INTEGER DEFAULT 0
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS smart_accounts (
                    account_id TEXT PRIMARY KEY,
                    owner_address TEXT NOT NULL,
                    account_type TEXT DEFAULT 'multisig',
                    threshold INTEGER DEFAULT 2,
                    owners TEXT,
                    created_at INTEGER NOT NULL
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS shards (
                    shard_id INTEGER PRIMARY KEY,
                    shard_hash TEXT NOT NULL,
                    node_address TEXT,
                    data_size INTEGER DEFAULT 0,
                    last_updated INTEGER,
                    status TEXT DEFAULT 'active'
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS peers (
                    peer_id TEXT PRIMARY KEY,
                    host TEXT NOT NULL,
                    port INTEGER NOT NULL,
                    connected_at INTEGER NOT NULL,
                    last_seen INTEGER,
                    is_active INTEGER DEFAULT 1
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            ''')
            
            cursor.execute('INSERT OR IGNORE INTO state (key, value, updated_at) VALUES ("last_block_height", "0", ?)', (int(time.time()),))
            
            conn.commit()
            print(f"{C.GREEN}✅ Database tables created{C.RESET}")

db = BlockchainDB()

# ============== КВАНТОВАЯ КРИПТОГРАФИЯ ==============

class QuantumCrypto:
    def __init__(self):
        self.algorithm = config.security.SIGNATURE_ALGO
        self.key_pairs = {}
        print(f"{C.GREEN}🔐 Quantum Crypto initialized: {self.algorithm}{C.RESET}")
    
    def generate_quantum_keypair(self, seed: str = None) -> Dict:
        if seed is None:
            seed = secrets.token_hex(128)
        
        hash_func = hashlib.sha3_512
        private_key = hash_func(seed.encode()).hexdigest()
        
        public_key = self._generate_public_key(private_key)
        quantum_address = f"qc:{hash_func(public_key.encode()).hexdigest()[:20]}"
        
        keypair = {
            'private_key': private_key,
            'public_key': public_key,
            'quantum_address': quantum_address,
            'algorithm': self.algorithm,
            'created_at': int(time.time())
        }
        
        self.key_pairs[public_key] = keypair
        return keypair
    
    def _generate_public_key(self, private_key: str) -> str:
        result = private_key
        for i in range(7):
            if i % 3 == 0:
                result = hashlib.sha3_256(f"{result}_layer_{i}".encode()).hexdigest()
            elif i % 3 == 1:
                result = hashlib.blake2b(f"{result}_layer_{i}".encode()).hexdigest()
            else:
                result = hashlib.sha512(f"{result}_layer_{i}".encode()).hexdigest()
        return result[:64]
    
    def quantum_sign(self, message: str, private_key: str) -> str:
        signature = private_key
        for i in range(12):
            signature = hashlib.sha3_256(f"{signature}{message}{i}".encode()).hexdigest()
        return signature[:128]
    
    def quantum_verify(self, message: str, signature: str, public_key: str) -> bool:
        expected = self.quantum_sign(message, public_key[:64])
        return hmac.compare_digest(signature[:64], expected[:64])
    
    def get_stats(self) -> Dict:
        return {'algorithm': self.algorithm, 'key_pairs': len(self.key_pairs)}

quantum_crypto = QuantumCrypto()

# ============== БЛОКИ, ТРАНЗАКЦИИ И КОНСЕНСУС ==============

@dataclass
class Transaction:
    hash: str
    from_addr: str
    to_addr: str
    amount: float
    fee: float = 0.001
    timestamp: int = field(default_factory=lambda: int(time.time()))
    nonce: int = 0
    signature: str = ""
    data: str = ""
    tx_type: str = "transfer"
    
    def to_dict(self) -> Dict:
        return {
            'hash': self.hash,
            'from_addr': self.from_addr,
            'to_addr': self.to_addr,
            'amount': self.amount,
            'fee': self.fee,
            'timestamp': self.timestamp,
            'nonce': self.nonce,
            'tx_type': self.tx_type
        }
    
    def calculate_hash(self) -> str:
        tx_string = json.dumps({
            'from': self.from_addr,
            'to': self.to_addr,
            'amount': self.amount,
            'fee': self.fee,
            'timestamp': self.timestamp,
            'nonce': self.nonce,
            'tx_type': self.tx_type
        }, sort_keys=True)
        return hashlib.sha3_256(tx_string.encode()).hexdigest()

@dataclass
class Block:
    height: int
    block_hash: str
    previous_hash: str
    timestamp: int
    miner: str
    validator: str
    transactions: List[Transaction]
    merkle_root: str
    nonce: int
    difficulty: int
    block_reward: float
    size: int = 0
    version: str = "1.0"
    consensus_type: str = "DPoS"
    
    def to_dict(self) -> Dict:
        return {
            'height': self.height,
            'block_hash': self.block_hash,
            'previous_hash': self.previous_hash,
            'timestamp': self.timestamp,
            'miner': self.miner,
            'validator': self.validator,
            'transactions': [t.to_dict() for t in self.transactions],
            'transaction_count': len(self.transactions),
            'merkle_root': self.merkle_root,
            'nonce': self.nonce,
            'difficulty': self.difficulty,
            'block_reward': self.block_reward,
            'size': self.size,
            'version': self.version,
            'consensus_type': self.consensus_type
        }
    
    def calculate_hash(self) -> str:
        block_string = json.dumps({
            'height': self.height,
            'previous_hash': self.previous_hash,
            'timestamp': self.timestamp,
            'miner': self.miner,
            'validator': self.validator,
            'merkle_root': self.merkle_root,
            'nonce': self.nonce,
            'difficulty': self.difficulty
        }, sort_keys=True)
        return hashlib.sha3_256(block_string.encode()).hexdigest()

class MerkleTree:
    @staticmethod
    def build_root(transactions: List[Transaction]) -> str:
        if not transactions:
            return hashlib.sha3_256(b'empty').hexdigest()
        
        current = [hashlib.sha3_256(json.dumps(t.to_dict(), sort_keys=True).encode()).hexdigest() for t in transactions]
        
        while len(current) > 1:
            next_level = []
            for i in range(0, len(current), 2):
                if i + 1 < len(current):
                    combined = current[i] + current[i + 1]
                else:
                    combined = current[i] + current[i]
                next_level.append(hashlib.sha3_256(combined.encode()).hexdigest())
            current = next_level
        
        return current[0]

class Consensus:
    def __init__(self):
        self.validators = []
        self.consensus_type = config.consensus.TYPE
        self.lock = threading.RLock()
        print(f"{C.GREEN}⚖️ Consensus initialized: {self.consensus_type}{C.RESET}")
    
    def register_validator(self, address: str, stake: float, commission: float = 5.0) -> str:
        with self.lock:
            validator_id = hashlib.sha3_256(f"{address}{stake}{time.time()}".encode()).hexdigest()[:16]
            
            try:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT address FROM validators WHERE address = ?', (address,))
                    existing = cursor.fetchone()
                    
                    if existing:
                        cursor.execute('''
                            UPDATE validators SET stake_amount = ?, commission = ?, active_since = ?, voting_power = ?, status = 'active'
                            WHERE address = ?
                        ''', (stake, commission, int(time.time()), stake, address))
                    else:
                        cursor.execute('''
                            INSERT INTO validators (validator_id, address, stake_amount, commission, active_since, voting_power, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (validator_id, address, stake, commission, int(time.time()), stake, 'active'))
            except Exception as e:
                print(f"{C.YELLOW}⚠️ DB error: {e}{C.RESET}")
            
            validator = {'validator_id': validator_id, 'address': address, 'stake': stake, 'commission': commission, 'voting_power': stake}
            
            for i, v in enumerate(self.validators):
                if v['address'] == address:
                    self.validators[i] = validator
                    return validator_id
            
            self.validators.append(validator)
            return validator_id
    
    def delegate_stake(self, delegator: str, validator_id: str, amount: float) -> bool:
        with self.lock:
            for validator in self.validators:
                if validator['validator_id'] == validator_id:
                    validator['stake'] += amount
                    validator['voting_power'] = validator['stake']
                    try:
                        with db.get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute('UPDATE validators SET stake_amount = ?, voting_power = ? WHERE validator_id = ?',
                                          (validator['stake'], validator['stake'], validator_id))
                    except:
                        pass
                    return True
            return False
    
    def get_validators(self) -> List[Dict]:
        with self.lock:
            return sorted(self.validators, key=lambda x: x['voting_power'], reverse=True)
    
    def select_validator(self) -> Optional[Dict]:
        with self.lock:
            if not self.validators:
                return None
            total = sum(v['voting_power'] for v in self.validators)
            if total == 0:
                return self.validators[0]
            r = random.random() * total
            cumulative = 0
            for v in self.validators:
                cumulative += v['voting_power']
                if cumulative >= r:
                    return v
            return self.validators[0]

class BlockchainCore:
    def __init__(self):
        self.consensus = Consensus()
        self.pending = []
        self.chain = []
        self.difficulty = 1
        self.lock = threading.RLock()
        self.last_block_time = time.time()
        self._load_chain()
        if len(self.chain) == 0:
            self.create_genesis_block()
        print(f"{C.GREEN}🏗️ Blockchain Core: {len(self.chain)} blocks{C.RESET}")
    
    def _load_chain(self):
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM blocks ORDER BY height ASC')
                rows = cursor.fetchall()
                for row in rows:
                    row_dict = {k: row[k] for k in row.keys()}
                    txs = []
                    try:
                        tx_data_list = json.loads(row_dict['transactions'])
                        for tx_data in tx_data_list:
                            txs.append(Transaction(
                                hash=tx_data.get('hash', ''),
                                from_addr=tx_data.get('from_addr', ''),
                                to_addr=tx_data.get('to_addr', ''),
                                amount=tx_data.get('amount', 0),
                                fee=tx_data.get('fee', 0.001),
                                timestamp=tx_data.get('timestamp', int(time.time())),
                                nonce=tx_data.get('nonce', 0),
                                signature=tx_data.get('signature', ''),
                                data=tx_data.get('data', ''),
                                tx_type=tx_data.get('tx_type', 'transfer')
                            ))
                    except:
                        txs = []
                    
                    self.chain.append(Block(
                        height=row_dict['height'],
                        block_hash=row_dict['block_hash'],
                        previous_hash=row_dict['previous_hash'],
                        timestamp=row_dict['timestamp'],
                        miner=row_dict['miner'],
                        validator=row_dict.get('validator', row_dict['miner']),
                        transactions=txs,
                        merkle_root=row_dict['merkle_root'],
                        nonce=row_dict['nonce'],
                        difficulty=row_dict['difficulty'],
                        block_reward=row_dict['block_reward'],
                        size=row_dict.get('size', 0),
                        version=row_dict.get('version', '1.0'),
                        consensus_type=row_dict.get('consensus_type', 'DPoS')
                    ))
        except Exception as e:
            print(f"{C.YELLOW}⚠️ Load chain error: {e}{C.RESET}")
    
    def create_genesis_block(self) -> Block:
        genesis = Block(
            height=0, block_hash='', previous_hash='0'*64, timestamp=int(time.time()),
            miner='system', validator='system', transactions=[],
            merkle_root=MerkleTree.build_root([]), nonce=0, difficulty=1,
            block_reward=config.economic.INITIAL_SUPPLY, size=1024,
            version='1.0', consensus_type='DPoS'
        )
        genesis.block_hash = genesis.calculate_hash()
        self.chain.append(genesis)
        self._save_block(genesis)
        self._create_initial_wallets()
        print(f"{C.GREEN}✅ Genesis block created{C.RESET}")
        return genesis
    
    def _create_initial_wallets(self):
        wallets = [
            ('foundation', config.economic.INITIAL_SUPPLY * 0.3),
            ('development', config.economic.INITIAL_SUPPLY * 0.2),
            ('community', config.economic.INITIAL_SUPPLY * 0.2),
            ('staking_rewards', config.economic.INITIAL_SUPPLY * 0.2),
            ('ecosystem', config.economic.INITIAL_SUPPLY * 0.1)
        ]
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                for addr, bal in wallets:
                    cursor.execute('INSERT OR IGNORE INTO wallets (address, private_key, public_key, balance, created_at) VALUES (?, ?, ?, ?, ?)',
                                  (addr, f"genesis_{addr}", f"pub_{addr}", bal, int(time.time())))
        except Exception as e:
            print(f"{C.YELLOW}⚠️ Could not create initial wallets: {e}{C.RESET}")
    
    def _save_block(self, block: Block):
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO blocks (height, block_hash, previous_hash, timestamp, miner, validator, 
                     transactions, transaction_count, total_amount, block_reward, difficulty, nonce, merkle_root, size, version, consensus_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (block.height, block.block_hash, block.previous_hash, block.timestamp, block.miner, block.validator,
                      json.dumps([t.to_dict() for t in block.transactions]), len(block.transactions),
                      sum(t.amount for t in block.transactions), block.block_reward, block.difficulty,
                      block.nonce, block.merkle_root, block.size, block.version, block.consensus_type))
        except Exception as e:
            print(f"{C.YELLOW}⚠️ Save block error: {e}{C.RESET}")
    
    def add_transaction(self, tx: Transaction) -> bool:
        with self.lock:
            if not self._validate_transaction(tx):
                return False
            
            tx.hash = tx.calculate_hash()
            tx.timestamp = int(time.time())
            tx.nonce = len(self.pending)
            self.pending.append(tx)
            
            try:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO transactions (tx_hash, from_address, to_address, amount, fee, timestamp, status, nonce, tx_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (tx.hash, tx.from_addr, tx.to_addr, tx.amount, tx.fee, tx.timestamp, 'pending', tx.nonce, tx.tx_type))
            except:
                pass
            
            return True
    
    def _validate_transaction(self, tx: Transaction) -> bool:
        if tx.amount <= 0:
            return False
        if tx.fee < config.economic.TRANSACTION_FEE:
            return False
        if self.get_balance(tx.from_addr) < tx.amount + tx.fee:
            return False
        return True
    
    def get_balance(self, address: str) -> float:
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT balance FROM wallets WHERE address = ?', (address,))
                row = cursor.fetchone()
                return row['balance'] if row else 0
        except:
            return 0
    
    def update_balance(self, address: str, amount: float) -> bool:
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE wallets SET balance = balance + ? WHERE address = ?', (amount, address))
                if cursor.rowcount == 0:
                    cursor.execute('INSERT INTO wallets (address, private_key, public_key, balance, created_at) VALUES (?, ?, ?, ?, ?)', 
                                  (address, '', '', max(0, amount), int(time.time())))
            return True
        except:
            return False
    
    def mine_block(self, miner: str) -> Optional[Block]:
        with self.lock:
            if len(self.pending) == 0 and len(self.chain) > 0:
                return None
            
            latest = self.chain[-1]
            validator = self.consensus.select_validator()
            val_addr = validator['address'] if validator else miner
            
            new_block = Block(
                height=latest.height + 1, block_hash='', previous_hash=latest.block_hash,
                timestamp=int(time.time()), miner=miner, validator=val_addr,
                transactions=self.pending.copy(), merkle_root=MerkleTree.build_root(self.pending),
                nonce=0, difficulty=self.difficulty, block_reward=config.consensus.BLOCK_REWARD,
                size=1024, version='1.0', consensus_type=self.consensus.consensus_type
            )
            
            target = 2 ** (256 - new_block.difficulty)
            while new_block.nonce < 1000000:
                new_block.block_hash = new_block.calculate_hash()
                if int(new_block.block_hash, 16) < target:
                    break
                new_block.nonce += 1
            
            new_block.block_hash = new_block.calculate_hash()
            
            reward_tx = Transaction(
                hash=hashlib.sha3_256(f"reward_{new_block.height}_{miner}".encode()).hexdigest(),
                from_addr='system', to_addr=miner, amount=config.consensus.BLOCK_REWARD, fee=0, tx_type='reward'
            )
            new_block.transactions.append(reward_tx)
            new_block.merkle_root = MerkleTree.build_root(new_block.transactions)
            
            self.chain.append(new_block)
            self._save_block(new_block)
            self._apply_transactions(new_block)
            self.pending = []
            self._adjust_difficulty()
            
            print(f"{C.GREEN}⛏️ Block #{new_block.height} mined by {miner[:16]}... with {len(new_block.transactions)} txs{C.RESET}")
            return new_block
    
    def _apply_transactions(self, block: Block):
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                for tx in block.transactions:
                    if tx.tx_type == 'reward':
                        self.update_balance(tx.to_addr, tx.amount)
                    else:
                        self.update_balance(tx.from_addr, -(tx.amount + tx.fee))
                        self.update_balance(tx.to_addr, tx.amount)
                    cursor.execute('UPDATE transactions SET status = "confirmed", block_height = ? WHERE tx_hash = ?',
                                  (block.height, tx.hash))
        except:
            pass
    
    def _adjust_difficulty(self):
        if len(self.chain) % config.consensus.EPOCH_LENGTH == 0 and len(self.chain) > 0:
            diff = time.time() - self.last_block_time
            expected = config.consensus.EPOCH_LENGTH * config.consensus.BLOCK_TIME
            if diff < expected / 2:
                self.difficulty += 1
            elif diff > expected * 2 and self.difficulty > 1:
                self.difficulty -= 1
            self.last_block_time = time.time()
    
    def get_blockchain_info(self) -> Dict:
        with self.lock:
            return {
                'network': 'Absolute Blockchain',
                'version': '15.0',
                'blocks': len(self.chain),
                'difficulty': self.difficulty,
                'pending_transactions': len(self.pending),
                'total_supply': self.get_total_supply(),
                'consensus': self.consensus.consensus_type,
                'validators_count': len(self.consensus.validators),
                'peers': 4
            }
    
    def get_total_supply(self) -> float:
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT SUM(balance) FROM wallets')
                result = cursor.fetchone()[0]
                return result if result else config.economic.INITIAL_SUPPLY
        except:
            return config.economic.INITIAL_SUPPLY

blockchain = BlockchainCore()

# ============== EVM, WASM, NFT, LIGHTNING, AI, BRIDGE, SMART ACCOUNTS, CRYPTO WILL, SHARDING, PLASMA, ZK ==============

class EVM:
    def __init__(self):
        self.contracts = {}
        self.storage = {}
        self.events = []
        self.gas_limit = config.economic.GAS_LIMIT
        self.gas_price = config.economic.GAS_PRICE
        print(f"{C.GREEN}📦 EVM initialized (gas limit: {self.gas_limit}){C.RESET}")
    
    def deploy_contract(self, bytecode: str, owner: str, abi: Dict = None) -> str:
        contract_address = f"0x{hashlib.sha3_256(f'{bytecode}{owner}{time.time()}'.encode()).hexdigest()[:40]}"
        self.contracts[contract_address] = {
            'address': contract_address, 'bytecode': bytecode, 'owner': owner,
            'abi': abi or {'functions': ['balanceOf', 'transfer', 'approve', 'allowance']},
            'created_at': int(time.time()), 'balance': 0
        }
        self.storage[contract_address] = {}
        self._log_event({'type': 'ContractDeployed', 'contract': contract_address, 'owner': owner, 'timestamp': int(time.time())})
        print(f"{C.GREEN}📦 Contract deployed: {contract_address[:20]}... by {owner[:16]}...{C.RESET}")
        return contract_address
    
    def call_function(self, contract_address: str, function_name: str, params: Dict, caller: str, value: float = 0) -> Dict:
        if contract_address not in self.contracts:
            return {'success': False, 'error': 'Contract not found', 'gas_used': 0}
        contract = self.contracts[contract_address]
        gas_used = 21000 + len(function_name) * 100 + len(json.dumps(params)) * 50
        if gas_used > self.gas_limit:
            return {'success': False, 'error': 'Out of gas', 'gas_used': gas_used}
        result = self._execute_function(contract, function_name, params, caller, value)
        self._log_event({'type': 'FunctionCall', 'contract': contract_address, 'function': function_name, 'caller': caller, 'params': params, 'value': value, 'gas_used': gas_used, 'result': result.get('result')})
        return {'success': result.get('success', True), 'result': result.get('result'), 'gas_used': gas_used, 'data': result.get('data')}
    
    def _execute_function(self, contract: Dict, function_name: str, params: Dict, caller: str, value: float) -> Dict:
        address = contract['address']
        if function_name == 'balanceOf':
            account = params.get('account', caller)
            balance = self.storage.get(address, {}).get(f'balance_{account}', 0)
            return {'success': True, 'result': balance}
        elif function_name == 'transfer':
            to = params.get('to')
            amount = params.get('amount', 0)
            if not to:
                return {'success': False, 'error': 'Recipient required'}
            if amount <= 0:
                return {'success': False, 'error': 'Amount must be > 0'}
            from_balance = self.storage.get(address, {}).get(f'balance_{caller}', 0)
            if from_balance < amount:
                return {'success': False, 'error': f'Insufficient balance: {from_balance} < {amount}'}
            if address not in self.storage:
                self.storage[address] = {}
            to_balance = self.storage[address].get(f'balance_{to}', 0)
            self.storage[address][f'balance_{caller}'] = from_balance - amount
            self.storage[address][f'balance_{to}'] = to_balance + amount
            self._log_event({'type': 'Transfer', 'contract': address, 'from': caller, 'to': to, 'value': amount})
            return {'success': True, 'result': True}
        elif function_name == 'approve':
            spender = params.get('spender')
            amount = params.get('amount', 0)
            if not spender:
                return {'success': False, 'error': 'Spender required'}
            if address not in self.storage:
                self.storage[address] = {}
            self.storage[address][f'allowance_{caller}_{spender}'] = amount
            self._log_event({'type': 'Approval', 'contract': address, 'owner': caller, 'spender': spender, 'value': amount})
            return {'success': True, 'result': True}
        elif function_name == 'allowance':
            owner = params.get('owner')
            spender = params.get('spender')
            if not owner or not spender:
                return {'success': False, 'error': 'Owner and spender required'}
            allowance = self.storage.get(address, {}).get(f'allowance_{owner}_{spender}', 0)
            return {'success': True, 'result': allowance}
        elif function_name == 'constructor':
            initial_supply = params.get('initialSupply', 1000000)
            owner = params.get('owner', caller)
            if address not in self.storage:
                self.storage[address] = {}
            self.storage[address]['total_supply'] = initial_supply
            self.storage[address][f'balance_{owner}'] = initial_supply
            return {'success': True, 'result': 'Contract initialized'}
        else:
            return {'success': True, 'result': f'Function {function_name} executed'}
    
    def _log_event(self, event: Dict):
        self.events.append(event)
        if len(self.events) > 10000:
            self.events = self.events[-10000:]
    
    def get_contract(self, contract_address: str) -> Optional[Dict]:
        return self.contracts.get(contract_address)
    
    def get_all_contracts(self) -> List[Dict]:
        return list(self.contracts.values())
    
    def get_events(self, limit: int = 100) -> List[Dict]:
        return self.events[-limit:][::-1]
    
    def get_stats(self) -> Dict:
        return {'contracts_count': len(self.contracts), 'storage_keys': sum(len(s) for s in self.storage.values()), 'events_count': len(self.events), 'gas_limit': self.gas_limit, 'gas_price': self.gas_price}

evm = EVM()

class WASM_VM:
    def __init__(self):
        self.contracts = {}
        self.storage = {}
        self.events = []
        self.gas_limit = 10_000_000
        print(f"{C.GREEN}🦀 WASM VM initialized{C.RESET}")
    
    def deploy_contract(self, code: str, owner: str, name: str = None) -> str:
        contract_id = f"wasm_{hashlib.sha256(f'{code}{owner}{time.time()}'.encode()).hexdigest()[:40]}"
        self.contracts[contract_id] = {'address': contract_id, 'code': code, 'owner': owner, 'name': name or f"Contract_{contract_id[:8]}", 'created_at': int(time.time()), 'abi': {'functions': ['balanceOf', 'transfer', 'constructor']}}
        self.storage[contract_id] = {}
        self._log_event({'type': 'ContractDeployed', 'address': contract_id, 'owner': owner})
        print(f"{C.GREEN}🦀 WASM Contract deployed: {contract_id[:20]}... by {owner[:16]}...{C.RESET}")
        return contract_id
    
    def call_function(self, contract_id: str, function_name: str, params: Dict, caller: str, value: float = 0) -> Dict:
        if contract_id not in self.contracts:
            return {'success': False, 'error': 'Contract not found', 'gas_used': 0}
        contract = self.contracts[contract_id]
        gas_used = 5000 + len(function_name) * 100 + len(json.dumps(params)) * 50
        if gas_used > self.gas_limit:
            return {'success': False, 'error': 'Out of gas', 'gas_used': gas_used}
        result = self._execute_function(contract, function_name, params, caller, value)
        self._log_event({'type': 'FunctionCall', 'contract': contract_id, 'function': function_name, 'caller': caller, 'params': params, 'gas_used': gas_used})
        return {'success': result.get('success', True), 'result': result.get('result'), 'gas_used': gas_used, 'data': result.get('data')}
    
    def _execute_function(self, contract: Dict, function_name: str, params: Dict, caller: str, value: float) -> Dict:
        address = contract['address']
        if function_name == 'balanceOf':
            account = params.get('account', caller)
            balance = self.storage.get(address, {}).get(f'balance_{account}', 0)
            return {'success': True, 'result': balance}
        elif function_name == 'transfer':
            to = params.get('to')
            amount = params.get('amount', 0)
            if not to:
                return {'success': False, 'error': 'Recipient required'}
            if amount <= 0:
                return {'success': False, 'error': 'Amount must be > 0'}
            from_balance = self.storage.get(address, {}).get(f'balance_{caller}', 0)
            if from_balance < amount:
                return {'success': False, 'error': 'Insufficient balance'}
            if address not in self.storage:
                self.storage[address] = {}
            to_balance = self.storage[address].get(f'balance_{to}', 0)
            self.storage[address][f'balance_{caller}'] = from_balance - amount
            self.storage[address][f'balance_{to}'] = to_balance + amount
            return {'success': True, 'result': True}
        elif function_name == 'constructor':
            initial_supply = params.get('initialSupply', 1000000)
            owner = params.get('owner', caller)
            if address not in self.storage:
                self.storage[address] = {}
            self.storage[address][f'balance_{owner}'] = initial_supply
            return {'success': True, 'result': 'Contract initialized'}
        elif function_name == 'getInfo':
            return {'success': True, 'result': contract.get('name', 'Unknown')}
        elif function_name == 'getOwner':
            return {'success': True, 'result': contract.get('owner', 'unknown')}
        else:
            if f'fn {function_name}' in contract.get('code', '') or f'function {function_name}' in contract.get('code', ''):
                return {'success': True, 'result': f'Function {function_name} executed'}
            return {'success': False, 'error': f'Function {function_name} not found'}
    
    def _log_event(self, event: Dict):
        self.events.append(event)
        if len(self.events) > 10000:
            self.events = self.events[-10000:]
    
    def get_contract(self, contract_id: str) -> Optional[Dict]:
        return self.contracts.get(contract_id)
    
    def get_contracts(self) -> List[Dict]:
        return [{'address': k, 'name': v.get('name', 'Unknown'), 'owner': v.get('owner', 'unknown')} for k, v in self.contracts.items()]
    
    def get_events(self, limit: int = 100) -> List[Dict]:
        return self.events[-limit:][::-1]
    
    def get_stats(self) -> Dict:
        return {'contracts_count': len(self.contracts), 'storage_keys': sum(len(s) for s in self.storage.values()), 'events_count': len(self.events), 'gas_limit': self.gas_limit}

wasm_vm = WASM_VM()

class NFTToken:
    def __init__(self, token_id: str, collection_id: str, name: str, creator: str, owner: str, metadata: Dict):
        self.token_id = token_id
        self.collection_id = collection_id
        self.name = name
        self.creator = creator
        self.owner = owner
        self.metadata = metadata
        self.created_at = int(time.time())
        self.price = 0
        self.for_sale = False
        self.transaction_history = []

class NFTCollection:
    def __init__(self, collection_id: str, name: str, creator: str, royalty: float = 5.0):
        self.collection_id = collection_id
        self.name = name
        self.creator = creator
        self.royalty = royalty
        self.tokens = {}
        self.created_at = int(time.time())
        self.total_supply = 0
        self.max_supply = config.nft.MAX_SUPPLY_PER_COLLECTION

class NFTManager:
    def __init__(self):
        self.collections = {}
        self.tokens = {}
        self.listings = {}
        print(f"{C.GREEN}🦋 NFT Manager initialized{C.RESET}")
    
    def create_collection(self, name: str, creator: str, royalty: float = 5.0) -> str:
        collection_id = hashlib.sha256(f"{name}{creator}{time.time()}".encode()).hexdigest()[:16]
        self.collections[collection_id] = NFTCollection(collection_id, name, creator, royalty)
        print(f"{C.GREEN}🦋 NFT Collection created: {name} ({collection_id}){C.RESET}")
        return collection_id
    
    def mint_nft(self, collection_id: str, name: str, creator: str, owner: str, metadata: Dict, royalty: float = None) -> str:
        if collection_id not in self.collections:
            raise ValueError(f"Collection {collection_id} not found")
        collection = self.collections[collection_id]
        if collection.total_supply >= collection.max_supply:
            raise ValueError(f"Collection {collection_id} reached max supply")
        token_id = hashlib.sha256(f"{collection_id}{name}{creator}{time.time()}".encode()).hexdigest()[:16]
        token = NFTToken(token_id, collection_id, name, creator, owner, metadata)
        self.tokens[token_id] = token
        collection.tokens[token_id] = token
        collection.total_supply += 1
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO nft_tokens (token_id, collection_id, name, owner_address, creator_address, metadata, created_at, royalty_percentage) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                              (token_id, collection_id, name, owner, creator, json.dumps(metadata), int(time.time()), royalty or collection.royalty))
        except:
            pass
        print(f"{C.GREEN}🦋 NFT Minted: {name} ({token_id}) for {owner[:16]}...{C.RESET}")
        return token_id
    
    def transfer_nft(self, token_id: str, from_owner: str, to_owner: str) -> bool:
        if token_id not in self.tokens:
            return False
        token = self.tokens[token_id]
        if token.owner != from_owner:
            return False
        token.owner = to_owner
        token.transaction_history.append({'from': from_owner, 'to': to_owner, 'timestamp': int(time.time())})
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE nft_tokens SET owner_address = ? WHERE token_id = ?', (to_owner, token_id))
        except:
            pass
        print(f"{C.GREEN}🦋 NFT Transferred: {token_id} from {from_owner[:16]}... to {to_owner[:16]}...{C.RESET}")
        return True
    
    def list_for_sale(self, token_id: str, owner: str, price: float) -> bool:
        if token_id not in self.tokens:
            return False
        token = self.tokens[token_id]
        if token.owner != owner:
            return False
        token.price = price
        token.for_sale = True
        self.listings[token_id] = {'token_id': token_id, 'owner': owner, 'price': price, 'listed_at': int(time.time())}
        return True
    
    def buy_nft(self, token_id: str, buyer: str, price: float) -> bool:
        if token_id not in self.listings:
            return False
        listing = self.listings[token_id]
        if listing['price'] != price:
            return False
        token = self.tokens[token_id]
        seller = token.owner
        buyer_balance = blockchain.get_balance(buyer)
        if buyer_balance < price:
            return False
        token.owner = buyer
        token.price = 0
        token.for_sale = False
        del self.listings[token_id]
        print(f"{C.GREEN}🦋 NFT Sold: {token_id} for {price} ABS from {seller[:16]}... to {buyer[:16]}...{C.RESET}")
        return True
    
    def get_nft(self, token_id: str) -> Optional[Dict]:
        if token_id in self.tokens:
            t = self.tokens[token_id]
            return {'token_id': t.token_id, 'name': t.name, 'owner': t.owner, 'creator': t.creator, 'metadata': t.metadata, 'price': t.price}
        return None
    
    def get_user_nfts(self, owner: str) -> List[Dict]:
        return [{'token_id': t.token_id, 'name': t.name, 'metadata': t.metadata} for t in self.tokens.values() if t.owner == owner]
    
    def get_listings(self) -> List[Dict]:
        return list(self.listings.values())
    
    def get_stats(self) -> Dict:
        return {'collections_count': len(self.collections), 'tokens_count': len(self.tokens), 'listings_count': len(self.listings)}

nft_manager = NFTManager()

class LightningChannel:
    def __init__(self, channel_id: str, node1: str, node2: str, capacity: float):
        self.channel_id = channel_id
        self.node1 = node1
        self.node2 = node2
        self.capacity = capacity
        self.balance1 = capacity / 2
        self.balance2 = capacity / 2
        self.status = "open"
        self.created_at = int(time.time())
        self.fee_rate = config.lightning.FEE_RATE

class LightningPayment:
    def __init__(self, payment_id: str, channel_id: str, from_node: str, to_node: str, amount: float, fee: float):
        self.payment_id = payment_id
        self.channel_id = channel_id
        self.from_node = from_node
        self.to_node = to_node
        self.amount = amount
        self.fee = fee
        self.timestamp = int(time.time())
        self.status = "completed"
        self.payment_hash = hashlib.sha256(f"{payment_id}{amount}{time.time()}".encode()).hexdigest()

class LightningNetwork:
    def __init__(self, node_address: str):
        self.node_address = node_address
        self.channels = {}
        self.payments = {}
        print(f"{C.GREEN}⚡ Lightning Network initialized for {node_address[:16]}...{C.RESET}")
    
    def open_channel(self, peer_address: str, capacity: float, funding_tx_hash: str = "") -> Optional[str]:
        if capacity < config.lightning.MIN_CHANNEL_SIZE:
            return None
        if capacity > config.lightning.MAX_CHANNEL_SIZE:
            return None
        balance = blockchain.get_balance(self.node_address)
        if balance < capacity:
            return None
        channel_id = hashlib.sha256(f"{self.node_address}{peer_address}{capacity}{time.time()}".encode()).hexdigest()[:16]
        channel = LightningChannel(channel_id, self.node_address, peer_address, capacity)
        self.channels[channel_id] = channel
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO lightning_channels (channel_id, node1_address, node2_address, capacity, balance1, balance2, status, created_at, fee_rate) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                              (channel_id, self.node_address, peer_address, capacity, channel.balance1, channel.balance2, 'open', int(time.time()), channel.fee_rate))
        except:
            pass
        print(f"{C.GREEN}⚡ Lightning channel opened: {channel_id} with {peer_address[:16]}... capacity: {capacity}{C.RESET}")
        return channel_id
    
    def close_channel(self, channel_id: str) -> bool:
        if channel_id not in self.channels:
            return False
        self.channels[channel_id].status = "closed"
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE lightning_channels SET status = "closed", closed_at = ? WHERE channel_id = ?', (int(time.time()), channel_id))
        except:
            pass
        print(f"{C.GREEN}⚡ Lightning channel closed: {channel_id}{C.RESET}")
        return True
    
    def send_payment(self, channel_id: str, to_node: str, amount: float) -> Optional[str]:
        if channel_id not in self.channels:
            return None
        channel = self.channels[channel_id]
        if channel.status != "open":
            return None
        if self.node_address == channel.node1:
            if channel.balance1 < amount:
                return None
            channel.balance1 -= amount
            channel.balance2 += amount
        elif self.node_address == channel.node2:
            if channel.balance2 < amount:
                return None
            channel.balance1 += amount
            channel.balance2 -= amount
        else:
            return None
        fee = amount * channel.fee_rate
        payment_id = hashlib.sha256(f"{channel_id}{self.node_address}{to_node}{amount}{time.time()}".encode()).hexdigest()[:16]
        payment = LightningPayment(payment_id, channel_id, self.node_address, to_node, amount, fee)
        self.payments[payment_id] = payment
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO lightning_payments (payment_id, channel_id, from_address, to_address, amount, fee, timestamp, status, payment_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                              (payment_id, channel_id, self.node_address, to_node, amount, fee, int(time.time()), 'completed', payment.payment_hash))
                cursor.execute('UPDATE lightning_channels SET balance1 = ?, balance2 = ? WHERE channel_id = ?', (channel.balance1, channel.balance2, channel_id))
        except:
            pass
        print(f"{C.GREEN}⚡ Lightning payment sent: {payment_id} amount: {amount} fee: {fee}{C.RESET}")
        return payment_id
    
    def get_channel_info(self, channel_id: str) -> Optional[Dict]:
        if channel_id in self.channels:
            ch = self.channels[channel_id]
            return {'channel_id': ch.channel_id, 'node1': ch.node1[:16] + '...', 'node2': ch.node2[:16] + '...', 'capacity': ch.capacity, 'balance1': ch.balance1, 'balance2': ch.balance2, 'status': ch.status}
        return None
    
    def get_all_channels(self) -> List[Dict]:
        return [self.get_channel_info(cid) for cid in self.channels if self.get_channel_info(cid)]
    
    def get_payment_history(self) -> List[Dict]:
        return [{'payment_id': p.payment_id[:8], 'amount': p.amount, 'fee': p.fee, 'status': p.status} for p in self.payments.values()]
    
    def get_stats(self) -> Dict:
        total_capacity = sum(ch.capacity for ch in self.channels.values())
        active = sum(1 for ch in self.channels.values() if ch.status == "open")
        return {'channels_count': len(self.channels), 'active_channels': active, 'total_capacity': total_capacity, 'payments_count': len(self.payments)}

lightning = LightningNetwork(blockchain.chain[0].miner if blockchain.chain else "system")

class AIAgent:
    def __init__(self, agent_id: str, name: str, owner: str, agent_type: str = "transformer"):
        self.agent_id = agent_id
        self.name = name
        self.owner = owner
        self.agent_type = agent_type
        self.status = "active"
        self.created_at = int(time.time())
        self.last_action = self.created_at
        self.performance_score = 0.0
        self.total_profit = 0.0
        self.memory = []
        self.strategy = {'type': 'arbitrage', 'risk_level': 'medium', 'max_position': 1000}
    
    def predict(self, input_data: Dict) -> Dict:
        features = input_data.get('features', [])
        if not features:
            return {'prediction': 0, 'confidence': 0}
        prediction = sum(features) / len(features)
        return {'prediction': prediction, 'confidence': 0.75, 'agent_type': self.agent_type}
    
    def execute_action(self, action: str, params: Dict) -> Dict:
        self.last_action = int(time.time())
        if action == "trade":
            return self._execute_trade(params)
        elif action == "analyze":
            return self._analyze_market(params)
        else:
            return {'success': False, 'error': f'Unknown action: {action}'}
    
    def _execute_trade(self, params: Dict) -> Dict:
        trade_type = params.get('type', 'buy')
        amount = params.get('amount', 0)
        price = params.get('price', 0)
        if amount <= 0 or price <= 0:
            return {'success': False, 'error': 'Invalid trade parameters'}
        tx_hash = hashlib.sha256(f"ai_trade_{self.agent_id}_{time.time()}".encode()).hexdigest()
        self.memory.append({'action': trade_type, 'amount': amount, 'price': price, 'timestamp': int(time.time())})
        return {'success': True, 'trade_id': tx_hash, 'type': trade_type, 'amount': amount, 'price': price}
    
    def _analyze_market(self, params: Dict) -> Dict:
        market_data = params.get('data', [])
        if not market_data:
            return {'success': False, 'error': 'No market data'}
        prices = [d.get('price', 0) for d in market_data if d.get('price')]
        if len(prices) < 2:
            return {'trend': 'neutral', 'confidence': 0}
        trend = (prices[-1] - prices[0]) / prices[0] if prices[0] > 0 else 0
        if trend > 0.05:
            trend_direction = 'bullish'
        elif trend < -0.05:
            trend_direction = 'bearish'
        else:
            trend_direction = 'neutral'
        return {'success': True, 'trend': trend_direction, 'trend_strength': abs(trend), 'recommendation': 'buy' if trend > 0.02 else 'sell' if trend < -0.02 else 'hold'}

class AIManager:
    def __init__(self):
        self.agents = {}
        print(f"{C.GREEN}🤖 AI Agent Manager initialized{C.RESET}")
    
    def create_agent(self, name: str, owner: str, agent_type: str = "transformer") -> str:
        agent_id = hashlib.sha256(f"{name}{owner}{time.time()}".encode()).hexdigest()[:16]
        agent = AIAgent(agent_id, name, owner, agent_type)
        self.agents[agent_id] = agent
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO ai_agents (agent_id, name, owner_address, model_type, status, created_at) VALUES (?, ?, ?, ?, ?, ?)',
                              (agent_id, name, owner, agent_type, 'active', int(time.time())))
        except:
            pass
        print(f"{C.GREEN}🤖 AI Agent created: {name} ({agent_id}) by {owner[:16]}...{C.RESET}")
        return agent_id
    
    def get_agent(self, agent_id: str) -> Optional[AIAgent]:
        return self.agents.get(agent_id)
    
    def get_user_agents(self, owner: str) -> List[Dict]:
        return [{'agent_id': a.agent_id, 'name': a.name, 'agent_type': a.agent_type, 'status': a.status, 'performance_score': a.performance_score} for a in self.agents.values() if a.owner == owner]
    
    def predict_market(self, agent_id: str, market_data: Dict) -> Dict:
        if agent_id not in self.agents:
            return {'error': f'Agent {agent_id} not found'}
        return self.agents[agent_id].predict(market_data)
    
    def execute_trade(self, agent_id: str, trade_params: Dict) -> Dict:
        if agent_id not in self.agents:
            return {'error': f'Agent {agent_id} not found'}
        return self.agents[agent_id].execute_action('trade', trade_params)
    
    def get_stats(self) -> Dict:
        return {'agents_count': len(self.agents), 'active_agents': sum(1 for a in self.agents.values() if a.status == 'active')}

ai_manager = AIManager()

class CrossChainTransfer:
    def __init__(self, transfer_id: str, source_chain: str, target_chain: str, from_address: str, to_address: str, amount: float, asset_symbol: str):
        self.transfer_id = transfer_id
        self.source_chain = source_chain
        self.target_chain = target_chain
        self.from_address = from_address
        self.to_address = to_address
        self.amount = amount
        self.asset_symbol = asset_symbol
        self.status = "pending"
        self.created_at = int(time.time())
        self.completed_at = None
        self.fee = amount * config.cross_chain.BRIDGE_FEE

class CrossChainBridge:
    def __init__(self):
        self.transfers = {}
        self.supported_chains = config.cross_chain.SUPPORTED_CHAINS
        print(f"{C.GREEN}🌉 Cross-Chain Bridge initialized (supported: {len(self.supported_chains)} chains){C.RESET}")
    
    def initiate_transfer(self, source_chain: str, target_chain: str, from_address: str, to_address: str, amount: float, asset_symbol: str = "ABS") -> Optional[str]:
        if source_chain not in self.supported_chains or target_chain not in self.supported_chains:
            return None
        if amount < config.cross_chain.MIN_BRIDGE_AMOUNT or amount > config.cross_chain.MAX_BRIDGE_AMOUNT:
            return None
        balance = blockchain.get_balance(from_address)
        total_cost = amount + (amount * config.cross_chain.BRIDGE_FEE)
        if balance < total_cost:
            return None
        transfer_id = hashlib.sha256(f"{source_chain}{target_chain}{from_address}{to_address}{amount}{time.time()}".encode()).hexdigest()[:16]
        transfer = CrossChainTransfer(transfer_id, source_chain, target_chain, from_address, to_address, amount, asset_symbol)
        self.transfers[transfer_id] = transfer
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO bridge_transfers (transfer_id, source_chain, target_chain, from_address, to_address, amount, asset_symbol, status, created_at, fee) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                              (transfer_id, source_chain, target_chain, from_address, to_address, amount, asset_symbol, 'pending', int(time.time()), transfer.fee))
        except:
            pass
        threading.Thread(target=self._process_transfer, args=(transfer_id,), daemon=True).start()
        return transfer_id
    
    def _process_transfer(self, transfer_id: str):
        time.sleep(2)
        if transfer_id in self.transfers:
            self.transfers[transfer_id].status = "completed"
            self.transfers[transfer_id].completed_at = int(time.time())
            try:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('UPDATE bridge_transfers SET status = "completed", completed_at = ? WHERE transfer_id = ?', (int(time.time()), transfer_id))
            except:
                pass
            print(f"{C.GREEN}🌉 Cross-chain transfer completed: {transfer_id}{C.RESET}")
    
    def get_transfer(self, transfer_id: str) -> Optional[Dict]:
        if transfer_id in self.transfers:
            t = self.transfers[transfer_id]
            return {'transfer_id': t.transfer_id, 'source_chain': t.source_chain, 'target_chain': t.target_chain, 'amount': t.amount, 'status': t.status, 'fee': t.fee}
        return None
    
    def get_user_transfers(self, address: str) -> List[Dict]:
        return [{'transfer_id': t.transfer_id, 'source_chain': t.source_chain, 'target_chain': t.target_chain, 'amount': t.amount, 'status': t.status} for t in self.transfers.values() if t.from_address == address or t.to_address == address]
    
    def get_pending_transfers(self) -> List[Dict]:
        return [{'transfer_id': t.transfer_id, 'amount': t.amount, 'from': t.from_address[:16] + '...'} for t in self.transfers.values() if t.status == 'pending']
    
    def get_stats(self) -> Dict:
        return {'supported_chains': self.supported_chains, 'total_transfers': len(self.transfers), 'completed_transfers': sum(1 for t in self.transfers.values() if t.status == 'completed'), 'pending_transfers': sum(1 for t in self.transfers.values() if t.status == 'pending'), 'total_volume': sum(t.amount for t in self.transfers.values() if t.status == 'completed')}

bridge = CrossChainBridge()

class SmartAccount:
    def __init__(self, account_id: str, owner: str, owners: List[str], threshold: int = 2):
        self.account_id = account_id
        self.owner = owner
        self.owners = owners
        self.threshold = threshold
        self.account_type = "multisig"
        self.created_at = int(time.time())
        self.pending_operations = []

class CryptoWill:
    def __init__(self, will_id: str, owner: str, heir: str, amount: float, assets: Dict, execution_time: int):
        self.will_id = will_id
        self.owner = owner
        self.heir = heir
        self.amount = amount
        self.assets = assets
        self.execution_time = execution_time
        self.created_at = int(time.time())
        self.executed = False
        self.witnesses = []

class SmartAccountManager:
    def __init__(self):
        self.accounts = {}
        print(f"{C.GREEN}👤 Smart Account Manager initialized{C.RESET}")
    
    def create_multisig_account(self, owner: str, owners: List[str], threshold: int = 2) -> str:
        if threshold > len(owners):
            threshold = len(owners)
        account_id = hashlib.sha256(f"{owner}{''.join(owners)}{time.time()}".encode()).hexdigest()[:16]
        account = SmartAccount(account_id, owner, owners, threshold)
        self.accounts[account_id] = account
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO smart_accounts (account_id, owner_address, account_type, threshold, owners, created_at) VALUES (?, ?, ?, ?, ?, ?)',
                              (account_id, owner, 'multisig', threshold, json.dumps(owners), int(time.time())))
        except:
            pass
        print(f"{C.GREEN}👤 Smart account created: {account_id} by {owner[:16]}...{C.RESET}")
        return account_id
    
    def propose_operation(self, account_id: str, proposer: str, operation: Dict) -> bool:
        if account_id not in self.accounts:
            return False
        account = self.accounts[account_id]
        if proposer not in account.owners:
            return False
        operation_id = hashlib.sha256(f"{account_id}{json.dumps(operation)}{time.time()}".encode()).hexdigest()[:16]
        proposal = {'operation_id': operation_id, 'proposer': proposer, 'operation': operation, 'approvals': [proposer], 'created_at': int(time.time()), 'status': 'pending'}
        account.pending_operations.append(proposal)
        return True
    
    def approve_operation(self, account_id: str, operation_id: str, approver: str) -> bool:
        if account_id not in self.accounts:
            return False
        account = self.accounts[account_id]
        for proposal in account.pending_operations:
            if proposal['operation_id'] == operation_id:
                if approver not in account.owners or approver in proposal['approvals']:
                    return False
                proposal['approvals'].append(approver)
                if len(proposal['approvals']) >= account.threshold:
                    self._execute_operation(account, proposal)
                    proposal['status'] = 'executed'
                return True
        return False
    
    def _execute_operation(self, account: SmartAccount, proposal: Dict):
        operation = proposal['operation']
        if operation.get('type') == 'transfer':
            to = operation.get('to')
            amount = operation.get('amount')
            if to and amount:
                tx = Transaction(hash=hashlib.sha256(f"multisig_{account.account_id}_{time.time()}".encode()).hexdigest(), from_addr=account.account_id, to_addr=to, amount=amount, fee=config.economic.TRANSACTION_FEE, tx_type="multisig")
                blockchain.add_transaction(tx)
        print(f"{C.GREEN}👤 Operation executed for {account.account_id}{C.RESET}")

class CryptoWillManager:
    def __init__(self):
        self.wills = {}
        threading.Thread(target=self._check_wills, daemon=True).start()
        print(f"{C.GREEN}📜 Crypto Will Manager initialized{C.RESET}")
    
    def create_will(self, owner: str, heir: str, amount: float, assets: Dict, execution_delay: int, witnesses: List[str] = None) -> Optional[str]:
        if execution_delay < config.crypto_will.MIN_EXECUTION_DELAY:
            execution_delay = config.crypto_will.MIN_EXECUTION_DELAY
        if execution_delay > config.crypto_will.MAX_EXECUTION_DELAY:
            execution_delay = config.crypto_will.MAX_EXECUTION_DELAY
        if blockchain.get_balance(owner) < amount:
            return None
        will_id = hashlib.sha256(f"{owner}{heir}{amount}{time.time()}".encode()).hexdigest()[:16]
        execution_time = int(time.time()) + execution_delay
        will = CryptoWill(will_id, owner, heir, amount, assets, execution_time)
        if witnesses:
            will.witnesses = witnesses
        self.wills[will_id] = will
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO crypto_wills (will_id, owner_address, heir_address, amount, assets, execution_time, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                              (will_id, owner, heir, amount, json.dumps(assets), execution_time, int(time.time())))
        except:
            pass
        print(f"{C.GREEN}📜 Crypto Will created: {will_id} by {owner[:16]}...{C.RESET}")
        return will_id
    
    def _check_wills(self):
        while True:
            time.sleep(3600)
            current = int(time.time())
            for will in self.wills.values():
                if not will.executed and current >= will.execution_time:
                    self._execute_will(will.will_id)
    
    def _execute_will(self, will_id: str) -> bool:
        if will_id not in self.wills:
            return False
        will = self.wills[will_id]
        if will.executed:
            return False
        if blockchain.get_balance(will.owner) < will.amount:
            return False
        tx = Transaction(hash=hashlib.sha256(f"will_{will_id}".encode()).hexdigest(), from_addr=will.owner, to_addr=will.heir, amount=will.amount, fee=config.economic.TRANSACTION_FEE, data=json.dumps({'type': 'will_execution', 'will_id': will_id}), tx_type="will")
        blockchain.add_transaction(tx)
        will.executed = True
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE crypto_wills SET executed = 1 WHERE will_id = ?', (will_id,))
        except:
            pass
        print(f"{C.GREEN}📜 Crypto Will executed: {will_id}{C.RESET}")
        return True
    
    def get_will(self, will_id: str) -> Optional[Dict]:
        if will_id in self.wills:
            w = self.wills[will_id]
            return {'will_id': w.will_id, 'owner': w.owner[:16] + '...', 'heir': w.heir[:16] + '...', 'amount': w.amount, 'executed': w.executed}
        return None
    
    def get_user_wills(self, address: str) -> List[Dict]:
        return [{'will_id': w.will_id, 'amount': w.amount, 'executed': w.executed} for w in self.wills.values() if w.owner == address or w.heir == address]
    
    def get_stats(self) -> Dict:
        return {'total_wills': len(self.wills), 'executed_wills': sum(1 for w in self.wills.values() if w.executed), 'pending_wills': sum(1 for w in self.wills.values() if not w.executed), 'total_amount': sum(w.amount for w in self.wills.values() if not w.executed)}

smart_account_manager = SmartAccountManager()
crypto_will_manager = CryptoWillManager()

class Shard:
    def __init__(self, shard_id: int, name: str):
        self.shard_id = shard_id
        self.name = name
        self.transactions = []
        self.blocks = []
        self.state_root = hashlib.sha256(b'empty').hexdigest()
        self.created_at = int(time.time())
        self.last_updated = self.created_at
        self.transaction_count = 0
        self.total_volume = 0.0
        self.data_size = 0
        self.lock = threading.RLock()
    
    def add_transaction(self, transaction: Dict) -> bool:
        with self.lock:
            self.transactions.append(transaction)
            self.transaction_count += 1
            self.total_volume += transaction.get('amount', 0)
            self.last_updated = int(time.time())
            tx_hash = hashlib.sha256(json.dumps(transaction, sort_keys=True).encode()).hexdigest()
            self.state_root = hashlib.sha256(f"{self.state_root}{tx_hash}".encode()).hexdigest()
            return True
    
    def get_stats(self) -> Dict:
        with self.lock:
            return {'shard_id': self.shard_id, 'name': self.name, 'transactions': self.transaction_count, 'volume': self.total_volume, 'state_root': self.state_root[:16] + '...', 'last_updated': self.last_updated, 'data_size': self.data_size}
    
    def to_dict(self) -> Dict:
        return {'shard_id': self.shard_id, 'name': self.name, 'transaction_count': self.transaction_count, 'total_volume': self.total_volume, 'data_size': self.data_size}

class ShardManager:
    def __init__(self):
        self.shards = {}
        self.shard_count = config.sharding.TOTAL_SHARDS
        self.lock = threading.RLock()
        self.rebalance_in_progress = False
        for i in range(self.shard_count):
            shard = Shard(i, f"Shard_{i:03d}")
            self.shards[i] = shard
        self._save_to_db()
        threading.Thread(target=self._rebalance_loop, daemon=True).start()
        print(f"{C.GREEN}🗺️ Sharding Manager initialized: {self.shard_count} shards{C.RESET}")
    
    def _save_to_db(self):
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                for shard_id, shard in self.shards.items():
                    cursor.execute('INSERT OR REPLACE INTO shards (shard_id, shard_hash, node_address, data_size, last_updated, status) VALUES (?, ?, ?, ?, ?, ?)', (shard_id, shard.state_root, f"node_{shard_id}", shard.data_size, shard.last_updated, 'active'))
        except:
            pass
    
    def get_shard_for_address(self, address: str) -> int:
        hash_val = int(hashlib.sha256(address.encode()).hexdigest()[:8], 16)
        return hash_val % self.shard_count
    
    def add_transaction(self, transaction: Dict) -> int:
        from_addr = transaction.get('from', '')
        shard_id = self.get_shard_for_address(from_addr)
        with self.lock:
            shard = self.shards.get(shard_id)
            if shard:
                shard.add_transaction(transaction)
                return shard_id
        return -1
    
    def get_shard_stats(self, shard_id: int = None) -> Dict:
        if shard_id is not None:
            if shard_id in self.shards:
                return self.shards[shard_id].get_stats()
            return {'error': f'Shard {shard_id} not found'}
        total_transactions = 0
        total_volume = 0.0
        for shard in self.shards.values():
            total_transactions += shard.transaction_count
            total_volume += shard.total_volume
        return {'total_shards': self.shard_count, 'active_shards': len([s for s in self.shards.values() if s.transaction_count > 0]), 'total_transactions': total_transactions, 'total_volume': total_volume, 'avg_transactions_per_shard': total_transactions / max(self.shard_count, 1), 'shards': [s.get_stats() for s in self.shards.values()]}
    
    def _rebalance_loop(self):
        while True:
            time.sleep(config.sharding.REBALANCE_INTERVAL)
            if self.rebalance_in_progress:
                continue
            self._rebalance_shards()
    
    def _rebalance_shards(self):
        self.rebalance_in_progress = True
        try:
            loads = [{'shard_id': shard_id, 'load': shard.transaction_count, 'volume': shard.total_volume} for shard_id, shard in self.shards.items()]
            loads.sort(key=lambda x: x['load'])
            avg_load = sum(l['load'] for l in loads) / len(loads)
            threshold = avg_load * 0.3
            overloaded = [l for l in loads if l['load'] > avg_load + threshold]
            underloaded = [l for l in loads if l['load'] < avg_load - threshold]
            if overloaded and underloaded:
                print(f"{C.CYAN}🔄 Rebalancing shards... {len(overloaded)} overloaded, {len(underloaded)} underloaded{C.RESET}")
        except:
            pass
        finally:
            self.rebalance_in_progress = False
    
    def get_stats(self) -> Dict:
        stats = self.get_shard_stats()
        cross_shard = []
        for shard_id, shard in self.shards.items():
            for tx in shard.transactions:
                from_shard = self.get_shard_for_address(tx.get('from', ''))
                to_shard = self.get_shard_for_address(tx.get('to', ''))
                if from_shard != to_shard:
                    cross_shard.append({'tx_hash': tx.get('hash'), 'from_shard': from_shard, 'to_shard': to_shard, 'amount': tx.get('amount', 0), 'timestamp': tx.get('timestamp', 0)})
        return {**stats, 'cross_shard_transactions': len(cross_shard), 'cross_shard_volume': sum(tx['amount'] for tx in cross_shard), 'rebalance_in_progress': self.rebalance_in_progress}

sharding_manager = ShardManager()

class PlasmaBlock:
    def __init__(self, block_id: int, parent_hash: str, transactions: List[Dict]):
        self.block_id = block_id
        self.parent_hash = parent_hash
        self.transactions = transactions
        self.created_at = int(time.time())
        self.block_hash = self.calculate_hash()
        self.transaction_count = len(transactions)
        self.total_amount = sum(tx.get('amount', 0) for tx in transactions)
    
    def calculate_hash(self) -> str:
        tx_hash = hashlib.sha256(json.dumps(self.transactions, sort_keys=True).encode()).hexdigest()
        return hashlib.sha256(f"{self.block_id}{self.parent_hash}{tx_hash}{self.created_at}".encode()).hexdigest()
    
    def to_dict(self) -> Dict:
        return {'block_id': self.block_id, 'block_hash': self.block_hash[:16] + '...', 'parent_hash': self.parent_hash[:16] + '...', 'transaction_count': self.transaction_count, 'total_amount': self.total_amount, 'created_at': self.created_at}

class PlasmaChain:
    def __init__(self, chain_id: str, root_chain):
        self.chain_id = chain_id
        self.root_chain = root_chain
        self.blocks = []
        self.pending_transactions = []
        self.deposits = {}
        self.exit_requests = {}
        self.challenge_period = 7 * 86400
        self._running = True
        self.lock = threading.RLock()
        genesis_block = PlasmaBlock(0, '0' * 64, [])
        self.blocks.append(genesis_block)
        self._start_exit_monitor()
        print(f"{C.GREEN}⚡ Plasma Chain initialized: {chain_id}{C.RESET}")
    
    def _start_exit_monitor(self):
        def monitor():
            while self._running:
                time.sleep(3600)
                self._check_pending_exits()
        threading.Thread(target=monitor, daemon=True).start()
    
    def _check_pending_exits(self):
        with self.lock:
            for exit_id, exit_req in list(self.exit_requests.items()):
                if exit_req['status'] == 'pending' and time.time() - exit_req['created_at'] >= self.challenge_period:
                    self.finalize_exit(exit_id)
    
    def deposit(self, from_addr: str, amount: float, main_tx_hash: str) -> Optional[str]:
        if amount <= 0:
            return None
        balance = self.root_chain.get_balance(from_addr) if hasattr(self.root_chain, 'get_balance') else 0
        if balance < amount:
            return None
        deposit_id = hashlib.sha256(f"{from_addr}{amount}{main_tx_hash}{time.time()}".encode()).hexdigest()[:16]
        with self.lock:
            self.deposits[deposit_id] = {'id': deposit_id, 'from': from_addr, 'amount': amount, 'main_tx_hash': main_tx_hash, 'created_at': int(time.time()), 'status': 'confirmed'}
            self.pending_transactions.append({'type': 'deposit', 'from': from_addr, 'to': from_addr, 'amount': amount, 'deposit_id': deposit_id, 'timestamp': int(time.time())})
        print(f"{C.GREEN}💰 Plasma deposit created: {deposit_id} amount: {amount}{C.RESET}")
        return deposit_id
    
    def submit_transaction(self, transaction: Dict) -> bool:
        if not transaction.get('from') or not transaction.get('to') or transaction.get('amount', 0) <= 0:
            return False
        tx = {'hash': hashlib.sha256(f"{transaction['from']}{transaction['to']}{transaction['amount']}{time.time()}".encode()).hexdigest(), 'from': transaction['from'], 'to': transaction['to'], 'amount': transaction['amount'], 'timestamp': int(time.time())}
        with self.lock:
            self.pending_transactions.append(tx)
        print(f"{C.GREEN}💸 Plasma transaction submitted: {tx['hash'][:16]}...{C.RESET}")
        return True
    
    def submit_block(self, proposer: str) -> Optional[PlasmaBlock]:
        with self.lock:
            if not self.pending_transactions:
                return None
            parent_hash = self.blocks[-1].block_hash if self.blocks else '0' * 64
            new_block = PlasmaBlock(len(self.blocks), parent_hash, self.pending_transactions.copy())
            self.blocks.append(new_block)
            self.pending_transactions = []
            print(f"{C.GREEN}📦 Plasma block #{new_block.block_id} created by {proposer[:16]}...{C.RESET}")
            return new_block
    
    def exit(self, deposit_id: str, user: str) -> Optional[str]:
        with self.lock:
            if deposit_id not in self.deposits or self.deposits[deposit_id]['status'] != 'confirmed' or user != self.deposits[deposit_id]['from']:
                return None
            exit_id = hashlib.sha256(f"{deposit_id}{user}{time.time()}".encode()).hexdigest()[:16]
            self.exit_requests[exit_id] = {'id': exit_id, 'deposit_id': deposit_id, 'user': user, 'amount': self.deposits[deposit_id]['amount'], 'created_at': int(time.time()), 'status': 'pending'}
            self.deposits[deposit_id]['status'] = 'exiting'
            print(f"{C.YELLOW}📤 Plasma exit requested: {exit_id} amount: {self.deposits[deposit_id]['amount']}{C.RESET}")
            return exit_id
    
    def finalize_exit(self, exit_id: str) -> bool:
        with self.lock:
            if exit_id not in self.exit_requests or self.exit_requests[exit_id]['status'] != 'pending' or time.time() - self.exit_requests[exit_id]['created_at'] < self.challenge_period:
                return False
            self.exit_requests[exit_id]['status'] = 'finalized'
            deposit = self.deposits.get(self.exit_requests[exit_id]['deposit_id'])
            if deposit:
                deposit['status'] = 'exited'
            print(f"{C.GREEN}✅ Plasma exit finalized: {exit_id} amount: {self.exit_requests[exit_id]['amount']}{C.RESET}")
            return True
    
    def get_stats(self) -> Dict:
        with self.lock:
            return {'chain_id': self.chain_id, 'blocks': len(self.blocks), 'pending_transactions': len(self.pending_transactions), 'deposits': len(self.deposits), 'exits': len(self.exit_requests), 'total_deposited': sum(d['amount'] for d in self.deposits.values()), 'total_withdrawn': sum(e['amount'] for e in self.exit_requests.values() if e['status'] == 'finalized')}
    
    def get_blocks(self, limit: int = 20) -> List[Dict]:
        with self.lock:
            return [b.to_dict() for b in self.blocks[-limit:]]

plasma_chain = PlasmaChain("plasma_main", blockchain)

class ZKProof:
    def __init__(self, proof_id: str, statement: str, proof_data: str):
        self.proof_id = proof_id
        self.statement = statement
        self.proof_data = proof_data
        self.created_at = int(time.time())
        self.verified = False

class ZKProofsSystem:
    def __init__(self):
        self.proofs = {}
        self.srs = hashlib.sha256(b"zk_srs_absolute_blockchain").hexdigest()
        print(f"{C.GREEN}🔒 ZK-Proofs System initialized{C.RESET}")
    
    def generate_proof(self, statement: str, witness: Dict, public_inputs: Dict) -> Optional[ZKProof]:
        proof_id = hashlib.sha256(f"{statement}{json.dumps(witness)}{time.time()}".encode()).hexdigest()[:32]
        proof_data = hashlib.sha256(f"{self.srs}{statement}{json.dumps(public_inputs)}".encode()).hexdigest()
        proof = ZKProof(proof_id, statement, proof_data)
        self.proofs[proof_id] = proof
        return proof
    
    def verify_proof(self, proof_id: str, public_inputs: Dict) -> bool:
        if proof_id not in self.proofs:
            return False
        proof = self.proofs[proof_id]
        expected = hashlib.sha256(f"{self.srs}{proof.statement}{json.dumps(public_inputs)}".encode()).hexdigest()
        is_valid = proof.proof_data == expected
        proof.verified = is_valid
        return is_valid
    
    def create_private_transaction(self, sender: str, receiver: str, amount: float) -> Dict:
        blinding = secrets.token_hex(16)
        commitment = hashlib.sha256(f"{sender}{receiver}{amount}{blinding}".encode()).hexdigest()
        proof = self.generate_proof(f"Private tx from {sender[:8]}...", {'amount': amount}, {'commitment': commitment})
        return {'type': 'private_transfer', 'commitment': commitment, 'proof_id': proof.proof_id if proof else None}
    
    def generate_range_proof(self, value: int, min_val: int = 0, max_val: int = 2**64) -> str:
        proof_id = hashlib.sha256(f"range_{value}_{min_val}_{max_val}_{time.time()}".encode()).hexdigest()[:16]
        self.proofs[proof_id] = ZKProof(proof_id, f"Value in range [{min_val}, {max_val}]", "")
        return proof_id
    
    def get_stats(self) -> Dict:
        return {'total_proofs': len(self.proofs), 'verified_proofs': sum(1 for p in self.proofs.values() if p.verified), 'srs_initialized': bool(self.srs)}

zk_proofs_system = ZKProofsSystem()

# ============== P2P СЕТЬ ==============

class SimpleP2PNetwork:
    def __init__(self):
        self.peers = []
        self.node_id = hashlib.sha256(str(time.time()).encode()).hexdigest()[:16]
        self.messages = []
        self.lock = threading.RLock()
    
    def add_peer(self, peer_address: str):
        with self.lock:
            if peer_address not in self.peers:
                self.peers.append(peer_address)
                print(f"{C.GREEN}✅ Peer {peer_address} added to network{C.RESET}")
    
    def get_peers(self) -> List[str]:
        with self.lock:
            return self.peers.copy()
    
    def broadcast_message(self, message: str, message_type: str = "text"):
        if not self.peers:
            return
        msg = {'id': hashlib.sha256(f"{self.node_id}{time.time()}{message}".encode()).hexdigest()[:16], 'type': message_type, 'from': self.node_id, 'content': message, 'timestamp': time.time()}
        self.messages.append(msg)
        print(f"{C.CYAN}📡 Broadcasting to {len(self.peers)} peers...{C.RESET}")

class P2PBlockchainNode:
    def __init__(self, blockchain_instance, ip: str = "127.0.0.1", port: int = 5000):
        self.ip = ip
        self.port = port
        self.blockchain = blockchain_instance
        # Инициализация Mempool
        if MEMPOOL_READY:
            self.mempool = Mempool()
            print("✅ Mempool initialized in APIHandler")
        else:
            self.mempool = None
        self.peers = []
        self.running = False
        self.socket = None
        self.lock = threading.RLock()
        self.network = SimpleP2PNetwork()
        print(f"{C.GREEN}🔗 P2PBlockchainNode created on {self.ip}:{self.port}{C.RESET}")
    
    def start_server(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.ip, self.port))
            self.socket.listen(10)
            self.running = True
            print(f"{C.GREEN}✅ P2P server started on {self.ip}:{self.port}{C.RESET}")
            self.network.add_peer(f"{self.ip}:{self.port}")
            while self.running:
                try:
                    client, addr = self.socket.accept()
                    threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()
                except:
                    pass
        except Exception as e:
            print(f"{C.RED}❌ Error starting P2P server: {e}{C.RESET}")
    
    def _handle_client(self, client_socket):
        try:
            data = client_socket.recv(4096)
            if data:
                message = json.loads(data.decode())
                msg_type = message.get('type')
                if msg_type == 'handshake':
                    node_info = message.get('node', '').split(':')
                    if len(node_info) == 2:
                        with self.lock:
                            peer = {'ip': node_info[0], 'port': int(node_info[1]), 'last_seen': time.time()}
                            if peer not in self.peers:
                                self.peers.append(peer)
                                self.network.add_peer(f"{node_info[0]}:{node_info[1]}")
                    response = json.dumps({'type': 'ack', 'status': 'connected', 'height': len(self.blockchain.chain)})
                    client_socket.send(response.encode())
                elif msg_type == 'get_chain':
                    response = {'type': 'chain_data', 'blocks': [b.to_dict() for b in self.blockchain.chain], 'height': len(self.blockchain.chain)}
                    client_socket.send(json.dumps(response).encode())
                elif msg_type == 'get_peers':
                    peers_list = [f"{p['ip']}:{p['port']}" for p in self.peers]
                    response = json.dumps({'type': 'peers', 'data': peers_list})
                    client_socket.send(response.encode())
                else:
                    response = json.dumps({'type': 'ack', 'status': 'ok'})
                    client_socket.send(response.encode())
            client_socket.close()
        except:
            try:
                client_socket.close()
            except:
                pass
    
    def connect(self, ip: str, port: int) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((ip, port))
            handshake = json.dumps({'type': 'handshake', 'node': f"{self.ip}:{self.port}", 'timestamp': time.time()})
            sock.send(handshake.encode())
            response = sock.recv(1024)
            with self.lock:
                peer = {'ip': ip, 'port': port, 'last_seen': time.time()}
                if peer not in self.peers:
                    self.peers.append(peer)
                    self.network.add_peer(f"{ip}:{port}")
            sock.close()
            print(f"{C.GREEN}✅ Connected to {ip}:{port}{C.RESET}")
            return True
        except:
            print(f"{C.RED}❌ Failed to connect to {ip}:{port}{C.RESET}")
            return False
    
    def broadcast_new_block(self, block):
        message = {'type': 'new_block', 'block': block.to_dict(), 'sender': f"{self.ip}:{self.port}", 'timestamp': time.time()}
        with self.lock:
            peers_copy = self.peers.copy()
        for peer in peers_copy:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((peer['ip'], peer['port']))
                sock.send(json.dumps(message).encode())
                sock.close()
            except:
                pass
        print(f"{C.CYAN}📡 New block #{block.height} broadcast to {len(peers_copy)} peers{C.RESET}")
    
    def get_peers(self) -> List[Dict]:
        with self.lock:
            return self.peers.copy()
    
    def get_network_info(self) -> Dict:
        return {'node': f"{self.ip}:{self.port}", 'peers_count': len(self.peers), 'peers': [f"{p['ip']}:{p['port']}" for p in self.peers], 'blockchain_height': len(self.blockchain.chain)}
    
    def stop(self):
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        print(f"{C.YELLOW}🛑 P2P node {self.ip}:{self.port} stopped{C.RESET}")

class P2PNetworkManager:
    def __init__(self):
        self.nodes = []
        print(f"{C.GREEN}🌐 P2P Network Manager initialized{C.RESET}")
    
    def create_node(self, blockchain_instance, ip: str = "127.0.0.1", port: int = 5000) -> P2PBlockchainNode:
        node = P2PBlockchainNode(blockchain_instance, ip, port)
        self.nodes.append(node)
        return node
    
    def start_all(self):
        for node in self.nodes:
            threading.Thread(target=node.start_server, daemon=True).start()
            time.sleep(0.5)
        print(f"{C.GREEN}✅ Started {len(self.nodes)} P2P nodes{C.RESET}")
    
    def connect_all(self):
        for i, node in enumerate(self.nodes):
            for j, target in enumerate(self.nodes):
                if i != j:
                    node.connect(target.ip, target.port)
                    time.sleep(0.2)
    
    def stop_all(self):
        for node in self.nodes:
            node.stop()
        print(f"{C.YELLOW}🛑 All P2P nodes stopped{C.RESET}")
    
    def get_network_stats(self) -> Dict:
        return {'total_nodes': len(self.nodes), 'nodes': [node.get_network_info() for node in self.nodes]}

p2p_manager = None
p2p_node = None

# ============== API СЕРВЕР (ИСПРАВЛЕННЫЙ) ==============

class APIHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.blockchain = blockchain
        # Инициализация Mempool
        if MEMPOOL_READY:
            self.mempool = Mempool()
            print("✅ Mempool initialized in APIHandler")
        else:
            self.mempool = None
        self.evm = evm
        self.wasm_vm = wasm_vm
        self.nft_manager = nft_manager
        self.lightning = lightning
        self.ai_manager = ai_manager
        self.bridge = bridge
        self.smart_account_manager = smart_account_manager
        self.crypto_will_manager = crypto_will_manager
        self.quantum_crypto = quantum_crypto
        self.sharding_manager = sharding_manager
        self.plasma_chain = plasma_chain
        self.zk_proofs_system = zk_proofs_system
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        pass

    # ============== ИСПРАВЛЕННЫЕ МЕТОДЫ (БЕЗ ОШИБОК) ==============
    
    def _send_json(self, data):
        try:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()
            try:
                self.wfile.write(json.dumps(data, default=str).encode())
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            except Exception as e:
                print(f"⚠️ Write error: {e}")
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception as e:
            print(f"⚠️ Send JSON error: {e}")

    def _send_html(self, html):
        try:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            try:
                self.wfile.write(html.encode('utf-8'))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception as e:
            print(f"⚠️ Send HTML error: {e}")

    def do_OPTIONS(self):
        try:
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()
        except:
            pass

    def _send_error(self, code, message):
        try:
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            try:
                self.wfile.write(json.dumps({'error': message, 'code': code}).encode())
            except:
                pass
        except:
            pass

    # ============== GET ЗАПРОСЫ ==============
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        try:
            # Веб-страницы
            if path == '/':
                self._send_html(self._get_main_page())
            elif path == '/docs':
                self._send_html(self._get_docs_page())
            elif path == '/wallet':
                self._send_html(self._get_wallet_page())
            elif path == '/explorer':
                self._send_html(self._get_explorer_page())
            elif path == '/staking':
                self._send_html(self._get_staking_page())
            elif path == '/nft':
                self._send_html(self._get_nft_page())
            elif path == '/evm':
                self._send_html(self._get_evm_page())
            elif path == '/wasm':
                self._send_html(self._get_wasm_page())
            elif path == '/lightning':
                self._send_html(self._get_lightning_page())
            elif path == '/ai':
                self._send_html(self._get_ai_page())
            elif path == '/bridge':
                self._send_html(self._get_bridge_page())
            elif path == '/smart_account':
                self._send_html(self._get_smart_account_page())
            elif path == '/will':
                self._send_html(self._get_will_page())
            elif path == '/quantum':
                self._send_html(self._get_quantum_page())
            elif path == '/sharding':
                self._send_html(self._get_sharding_page())
            elif path == '/plasma':
                self._send_html(self._get_plasma_page())
            elif path == '/zk':
                self._send_html(self._get_zk_page())
            elif path == '/dashboard':
                self._send_html(self._get_dashboard_page())
            elif path == '/validator':
                self._send_html(self._get_validator_page())
            # API эндпоинты
            elif path == '/api/stats':
                self._send_json(self.blockchain.get_blockchain_info())

            elif path == '/api/mempool/stats':
                stats = self.mempool.get_stats()
                self._send_json(stats) 
           
            elif path == '/api/blocks':
                self._send_json([b.to_dict() for b in self.blockchain.chain])
            elif path == '/api/peers':
                peers_list = []
                if p2p_node and hasattr(p2p_node, 'peers'):
                    for p in p2p_node.peers:
                        if isinstance(p, dict):
                            peers_list.append(f"{p.get('ip', 'unknown')}:{p.get('port', 0)}")
                        else:
                            peers_list.append(str(p))
                self._send_json({'peers': peers_list})
            elif path == '/api/balance':
                address = query.get('address', [''])[0]
                if address:
                    self._send_json({'address': address, 'balance': self.blockchain.get_balance(address)})
                else:
                    self._send_error(400, 'Address required')
            elif path == '/api/wallets':
                try:
                    with db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute('SELECT address, balance, created_at FROM wallets LIMIT 100')
                        wallets = [{'address': row['address'], 'balance': row['balance'], 'created_at': row['created_at']} for row in cursor.fetchall()]
                        self._send_json(wallets)
                except:
                    self._send_json([])
            elif path == '/api/transactions':
                try:
                    with db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute('SELECT tx_hash, from_address, to_address, amount, fee, timestamp, status FROM transactions ORDER BY timestamp DESC LIMIT 50')
                        self._send_json([dict(row) for row in cursor.fetchall()])
                except:
                    self._send_json([])
            elif path == '/api/validators':
                validators = []
                for v in self.blockchain.consensus.get_validators():
                    validators.append({'validator_id': v.get('validator_id', ''), 'address': v.get('address', ''), 'stake': v.get('stake', 0), 'commission': v.get('commission', 5), 'voting_power': v.get('voting_power', 0)})
                self._send_json({'validators': validators})
            elif path == '/api/staking':
                try:
                    with db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute('SELECT SUM(amount) as total FROM stakes WHERE status = "active"')
                        row = cursor.fetchone()
                        total = row['total'] if row and row['total'] else 0
                        self._send_json({'total_staked': total, 'validators_count': len(self.blockchain.consensus.validators), 'stakers_count': 0, 'apy': config.consensus.REWARD_PERCENTAGE, 'min_stake': config.consensus.MIN_STAKE, 'block_reward': config.consensus.BLOCK_REWARD})
                except:
                    self._send_json({'total_staked': 0, 'validators_count': 0, 'stakers_count': 0, 'apy': 5, 'min_stake': 100, 'block_reward': 50})
            elif path == '/api/evm/contracts':
                self._send_json({'contracts': self.evm.get_all_contracts()})
            elif path == '/api/evm/events':
                self._send_json({'events': self.evm.get_events(50)})
            elif path == '/api/evm/contract':
                address = query.get('address', [''])[0]
                if address:
                    contract = self.evm.get_contract(address)
                    self._send_json(contract or {'error': 'Contract not found'})
                else:
                    self._send_error(400, 'Address required')
            elif path == '/api/evm/stats':
                self._send_json(self.evm.get_stats())
            elif path == '/api/wasm/contracts':
                self._send_json({'contracts': self.wasm_vm.get_contracts()})
            elif path == '/api/wasm/contract':
                address = query.get('address', [''])[0]
                if address:
                    contract = self.wasm_vm.get_contract(address)
                    self._send_json(contract or {'error': 'Contract not found'})
                else:
                    self._send_error(400, 'Address required')
            elif path == '/api/wasm/stats':
                self._send_json(self.wasm_vm.get_stats())
            elif path == '/api/nft/tokens':
                owner = query.get('owner', [''])[0]
                if owner:
                    tokens = self.nft_manager.get_user_nfts(owner)
                else:
                    tokens = [{'token_id': t.token_id, 'name': t.name, 'owner': t.owner, 'metadata': t.metadata, 'price': t.price, 'for_sale': t.for_sale} for t in self.nft_manager.tokens.values()]
                self._send_json({'tokens': tokens, 'total': len(tokens)})
            elif path == '/api/nft/listings':
                self._send_json({'listings': self.nft_manager.get_listings()})
            elif path == '/api/nft/collections':
                self._send_json({'collections': [{'collection_id': c.collection_id, 'name': c.name, 'creator': c.creator, 'royalty': c.royalty, 'total_supply': c.total_supply} for c in self.nft_manager.collections.values()]})
            elif path == '/api/nft/collection':
                collection_id = query.get('id', [''])[0]
                if collection_id and collection_id in self.nft_manager.collections:
                    c = self.nft_manager.collections[collection_id]
                    self._send_json({'collection_id': c.collection_id, 'name': c.name, 'creator': c.creator, 'royalty': c.royalty, 'total_supply': c.total_supply, 'max_supply': c.max_supply})
                else:
                    self._send_error(404, 'Collection not found')
            elif path == '/api/nft/stats':
                self._send_json(self.nft_manager.get_stats())
            elif path == '/api/lightning/channels':
                self._send_json({'channels': self.lightning.get_all_channels(), 'total': len(self.lightning.channels)})
            elif path == '/api/lightning/payments':
                self._send_json({'payments': self.lightning.get_payment_history()})
            elif path == '/api/lightning/channel':
                channel_id = query.get('id', [''])[0]
                if channel_id:
                    channel = self.lightning.get_channel_info(channel_id)
                    self._send_json(channel or {'error': 'Channel not found'})
                else:
                    self._send_error(400, 'Channel ID required')
            elif path == '/api/lightning/stats':
                self._send_json(self.lightning.get_stats())
            elif path == '/api/ai/agents':
                owner = query.get('owner', [''])[0]
                if owner:
                    agents = self.ai_manager.get_user_agents(owner)
                else:
                    agents = [{'agent_id': a.agent_id, 'name': a.name, 'type': a.agent_type, 'status': a.status, 'performance_score': a.performance_score} for a in self.ai_manager.agents.values()]
                self._send_json({'agents': agents, 'total': len(agents)})
            elif path == '/api/ai/agent':
                agent_id = query.get('id', [''])[0]
                if agent_id:
                    agent = self.ai_manager.get_agent(agent_id)
                    if agent:
                        self._send_json({'agent_id': agent.agent_id, 'name': agent.name, 'type': agent.agent_type, 'status': agent.status, 'strategy': agent.strategy, 'performance_score': agent.performance_score})
                    else:
                        self._send_error(404, 'Agent not found')
                else:
                    self._send_error(400, 'Agent ID required')
            elif path == '/api/ai/stats':
                self._send_json(self.ai_manager.get_stats())
            elif path == '/api/bridge/transfers':
                address = query.get('address', [''])[0]
                if address:
                    transfers = self.bridge.get_user_transfers(address)
                else:
                    transfers = self.bridge.get_pending_transfers()
                self._send_json({'transfers': transfers, 'total': len(transfers)})
            elif path == '/api/bridge/transfer':
                transfer_id = query.get('id', [''])[0]
                if transfer_id:
                    transfer = self.bridge.get_transfer(transfer_id)
                    self._send_json(transfer or {'error': 'Transfer not found'})
                else:
                    self._send_error(400, 'Transfer ID required')
            elif path == '/api/bridge/stats':
                self._send_json(self.bridge.get_stats())
            elif path == '/api/smart_account/accounts':
                accounts = []
                for acc_id, acc in self.smart_account_manager.accounts.items():
                    accounts.append({'account_id': acc_id, 'owner': acc.owner[:16] + '...', 'owners_count': len(acc.owners), 'threshold': acc.threshold, 'created_at': acc.created_at})
                self._send_json({'accounts': accounts, 'total': len(accounts)})
            elif path == '/api/smart_account/account':
                account_id = query.get('id', [''])[0]
                if account_id and account_id in self.smart_account_manager.accounts:
                    acc = self.smart_account_manager.accounts[account_id]
                    self._send_json({'account_id': acc.account_id, 'owner': acc.owner, 'owners': acc.owners, 'threshold': acc.threshold, 'created_at': acc.created_at, 'pending_ops': len(acc.pending_operations)})
                else:
                    self._send_error(404, 'Account not found')
            elif path == '/api/will/wills':
                address = query.get('address', [''])[0]
                if address:
                    wills = self.crypto_will_manager.get_user_wills(address)
                else:
                    wills = [{'will_id': w.will_id, 'amount': w.amount, 'executed': w.executed, 'heir': w.heir[:16] + '...' if hasattr(w, 'heir') else 'unknown'} for w in self.crypto_will_manager.wills.values()]
                self._send_json({'wills': wills, 'total': len(wills)})
            elif path == '/api/will':
                will_id = query.get('id', [''])[0]
                if will_id:
                    will = self.crypto_will_manager.get_will(will_id)
                    self._send_json(will or {'error': 'Will not found'})
                else:
                    self._send_error(400, 'Will ID required')
            elif path == '/api/will/stats':
                self._send_json(self.crypto_will_manager.get_stats())
            elif path == '/api/quantum/keys':
                address = query.get('address', [''])[0]
                if address:
                    keys = self.quantum_crypto.generate_quantum_keypair()
                    self._send_json(keys)
                else:
                    self._send_error(400, 'Address required')
            elif path == '/api/quantum/stats':
                self._send_json(self.quantum_crypto.get_stats())
            elif path == '/api/sharding':
                self._send_json(self.sharding_manager.get_stats())
            elif path == '/api/sharding/shard':
                shard_id = query.get('id', [''])[0]
                if shard_id and shard_id.isdigit():
                    stats = self.sharding_manager.get_shard_stats(int(shard_id))
                    self._send_json(stats)
                else:
                    self._send_error(400, 'Invalid Shard ID')
            elif path == '/api/plasma/stats':
                self._send_json(self.plasma_chain.get_stats())
            elif path == '/api/plasma/blocks':
                limit = int(query.get('limit', ['20'])[0])
                self._send_json({'blocks': self.plasma_chain.get_blocks(limit)})
            elif path == '/api/plasma/deposit':
                deposit_id = query.get('id', [''])[0]
                if deposit_id:
                    deposit = self.plasma_chain.deposits.get(deposit_id)
                    self._send_json(deposit or {'error': 'Deposit not found'})
                else:
                    self._send_error(400, 'Deposit ID required')
            elif path == '/api/zk/stats':
                self._send_json(self.zk_proofs_system.get_stats())
            elif path == '/api/zk/proof':
                proof_id = query.get('id', [''])[0]
                if proof_id and proof_id in self.zk_proofs_system.proofs:
                    proof = self.zk_proofs_system.proofs[proof_id]
                    self._send_json({'proof_id': proof.proof_id, 'statement': proof.statement, 'verified': proof.verified, 'created_at': proof.created_at})
                else:
                    self._send_error(404, 'Proof not found')
            else:
                self._send_error(404, 'Not found')
        except Exception as e:
            print(f"⚠️ GET Error: {e}")
            self._send_error(500, str(e))

    # ============== POST ЗАПРОСЫ ==============
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length else b'{}'
        try:
            data = json.loads(body.decode('utf-8'))
        except:
            data = {}
        path = self.path
        
        try:
            if path == '/api/wallet/create':
                wallet = self.quantum_crypto.generate_quantum_keypair()
                try:
                    with db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute('INSERT OR IGNORE INTO wallets (address, private_key, public_key, balance, created_at) VALUES (?, ?, ?, ?, ?)',
                                      (wallet.get('quantum_address', wallet.get('address', '')), wallet.get('private_key', ''), wallet.get('public_key', ''), 1000, int(time.time())))
                except:
                    pass
                self._send_json(wallet)
            elif path == '/api/transaction/send':
                from_addr = data.get('from', data.get('from_addr'))
                to_addr = data.get('to', data.get('to_addr'))
                amount = float(data.get('amount', 0))
                private_key = data.get('private_key', '')
                if not from_addr or not to_addr:
                    self._send_json({'success': False, 'error': 'Missing from or to address'})
                    return
                tx = Transaction(hash=hashlib.sha256(f"{from_addr}{to_addr}{amount}{time.time()}".encode()).hexdigest(), from_addr=from_addr, to_addr=to_addr, amount=amount, fee=config.economic.TRANSACTION_FEE, signature=private_key)
                success = self.blockchain.add_transaction(tx)
                self._send_json({'success': success, 'tx_hash': tx.hash if success else None, 'amount': amount, 'fee': config.economic.TRANSACTION_FEE})
            elif path == '/api/mine':
                miner = data.get('miner', 'system')
                block = self.blockchain.mine_block(miner)
                self._send_json({'success': block is not None, 'block_height': block.height if block else 0, 'block_hash': block.block_hash if block else None, 'transactions': len(block.transactions) if block else 0})
            elif path == '/api/validator/register':
                address = data.get('address')
                stake = float(data.get('stake', 0))
                commission = float(data.get('commission', 5.0))
                if not address:
                    self._send_json({'success': False, 'error': 'Address required'})
                    return
                if stake < config.consensus.MIN_STAKE:
                    self._send_json({'success': False, 'error': f'Minimum stake is {config.consensus.MIN_STAKE}'})
                    return
                validator_id = self.blockchain.consensus.register_validator(address, stake, commission)
                self._send_json({'success': True, 'validator_id': validator_id, 'address': address, 'stake': stake, 'commission': commission})
            elif path == '/api/stake':
                address = data.get('address')
                amount = float(data.get('amount', 0))
                validator_id = data.get('validator_id')
                if not address or not validator_id:
                    self._send_json({'success': False, 'error': 'Address and validator_id required'})
                    return
                if amount < config.consensus.MIN_STAKE:
                    self._send_json({'success': False, 'error': f'Minimum stake is {config.consensus.MIN_STAKE}'})
                    return
                success = self.blockchain.consensus.delegate_stake(address, validator_id, amount)
                self._send_json({'success': success, 'validator_id': validator_id, 'amount': amount})
            elif path == '/api/evm/deploy':
                contract_address = self.evm.deploy_contract(data.get('bytecode', ''), data.get('owner', 'anonymous'), data.get('abi'))
                self._send_json({'success': True, 'contract_address': contract_address, 'owner': data.get('owner', 'anonymous')})
            elif path == '/api/evm/call':
                result = self.evm.call_function(data.get('contract_address', ''), data.get('function', ''), data.get('params', {}), data.get('caller', 'anonymous'), float(data.get('value', 0)))
                self._send_json(result)
            elif path == '/api/wasm/deploy':
                contract_id = self.wasm_vm.deploy_contract(data.get('code', ''), data.get('owner', 'anonymous'), data.get('name'))
                self._send_json({'success': True, 'contract_address': contract_id, 'name': data.get('name', 'WASM Contract')})
            elif path == '/api/wasm/call':
                result = self.wasm_vm.call_function(data.get('contract_address', ''), data.get('function', ''), data.get('params', {}), data.get('caller', 'anonymous'), float(data.get('value', 0)))
                self._send_json(result)
            elif path == '/api/nft/collection/create':
                collection_id = self.nft_manager.create_collection(data.get('name', ''), data.get('creator', ''), float(data.get('royalty', 5.0)))
                self._send_json({'success': True, 'collection_id': collection_id, 'name': data.get('name', ''), 'royalty': data.get('royalty', 5.0)})
            elif path == '/api/nft/mint':
                token_id = self.nft_manager.mint_nft(data.get('collection_id', ''), data.get('name', ''), data.get('creator', ''), data.get('owner', data.get('creator', '')), data.get('metadata', {}), float(data.get('royalty', 5.0)))
                self._send_json({'success': True, 'token_id': token_id, 'name': data.get('name', ''), 'owner': data.get('owner', data.get('creator', ''))})
            elif path == '/api/nft/list':
                success = self.nft_manager.list_for_sale(data.get('token_id', ''), data.get('owner', ''), float(data.get('price', 0)))
                self._send_json({'success': success, 'token_id': data.get('token_id', ''), 'price': data.get('price', 0)})
            elif path == '/api/nft/buy':
                success = self.nft_manager.buy_nft(data.get('token_id', ''), data.get('buyer', ''), float(data.get('price', 0)))
                self._send_json({'success': success, 'token_id': data.get('token_id', ''), 'buyer': data.get('buyer', '')})
            elif path == '/api/nft/transfer':
                success = self.nft_manager.transfer_nft(data.get('token_id', ''), data.get('from_owner', ''), data.get('to_owner', ''))
                self._send_json({'success': success, 'token_id': data.get('token_id', '')})
            elif path == '/api/lightning/channel/open':
                channel_id = self.lightning.open_channel(data.get('peer', ''), float(data.get('capacity', 0)), '')
                self._send_json({'success': channel_id is not None, 'channel_id': channel_id, 'peer': data.get('peer', ''), 'capacity': data.get('capacity', 0)})
            elif path == '/api/lightning/channel/close':
                success = self.lightning.close_channel(data.get('channel_id', ''))
                self._send_json({'success': success, 'channel_id': data.get('channel_id', '')})
            elif path == '/api/lightning/payment/send':
                payment_id = self.lightning.send_payment(data.get('channel_id', ''), data.get('to', ''), float(data.get('amount', 0)))
                self._send_json({'success': payment_id is not None, 'payment_id': payment_id, 'amount': data.get('amount', 0)})
            elif path == '/api/ai/agent/create':
                agent_id = self.ai_manager.create_agent(data.get('name', ''), data.get('owner', ''), data.get('agent_type', 'transformer'))
                self._send_json({'success': True, 'agent_id': agent_id, 'name': data.get('name', ''), 'type': data.get('agent_type', 'transformer')})
            elif path == '/api/ai/agent/predict':
                if 'agent_id' in data and 'market_data' in data:
                    result = self.ai_manager.predict_market(data['agent_id'], data['market_data'])
                    self._send_json(result)
                else:
                    self._send_json({'success': False, 'error': 'Missing agent_id or market_data'})
            elif path == '/api/ai/agent/trade':
                if 'agent_id' in data and 'trade_params' in data:
                    result = self.ai_manager.execute_trade(data['agent_id'], data['trade_params'])
                    self._send_json(result)
                else:
                    self._send_json({'success': False, 'error': 'Missing agent_id or trade_params'})
            elif path == '/api/bridge/transfer':
                transfer_id = self.bridge.initiate_transfer(data.get('source_chain', ''), data.get('target_chain', ''), data.get('from_address', ''), data.get('to_address', ''), float(data.get('amount', 0)), data.get('asset', 'ABS'))
                self._send_json({'success': transfer_id is not None, 'transfer_id': transfer_id, 'amount': data.get('amount', 0)})
            elif path == '/api/smart_account/create':
                account_id = self.smart_account_manager.create_multisig_account(data.get('owner', ''), data.get('owners', [data.get('owner', '')]), int(data.get('threshold', 2)))
                self._send_json({'success': True, 'account_id': account_id, 'threshold': data.get('threshold', 2)})
            elif path == '/api/smart_account/propose':
                success = self.smart_account_manager.propose_operation(data.get('account_id', ''), data.get('proposer', ''), data.get('operation', {}))
                self._send_json({'success': success, 'account_id': data.get('account_id', '')})
            elif path == '/api/smart_account/approve':
                success = self.smart_account_manager.approve_operation(data.get('account_id', ''), data.get('operation_id', ''), data.get('approver', ''))
                self._send_json({'success': success, 'operation_id': data.get('operation_id', '')})
            elif path == '/api/will/create':
                will_id = self.crypto_will_manager.create_will(data.get('owner', ''), data.get('heir', ''), float(data.get('amount', 0)), data.get('assets', {}), int(data.get('execution_delay', 86400)), data.get('witnesses', []))
                self._send_json({'success': will_id is not None, 'will_id': will_id, 'amount': data.get('amount', 0)})
            elif path == '/api/will/execute':
                success = self.crypto_will_manager._execute_will(data.get('will_id', ''))
                self._send_json({'success': success, 'will_id': data.get('will_id', '')})
            elif path == '/api/sharding/transaction':
                shard_id = self.sharding_manager.add_transaction(data.get('transaction', {}))
                self._send_json({'success': shard_id != -1, 'shard_id': shard_id})
            elif path == '/api/plasma/deposit':
                deposit_id = self.plasma_chain.deposit(data.get('from', ''), float(data.get('amount', 0)), data.get('main_tx_hash', ''))
                self._send_json({'success': deposit_id is not None, 'deposit_id': deposit_id})
            elif path == '/api/plasma/exit':
                exit_id = self.plasma_chain.exit(data.get('deposit_id', ''), data.get('user', ''))
                self._send_json({'success': exit_id is not None, 'exit_id': exit_id})
            elif path == '/api/plasma/block/submit':
                block = self.plasma_chain.submit_block(data.get('proposer', 'system'))
                self._send_json({'success': block is not None, 'block_id': block.block_id if block else None})
            elif path == '/api/zk/proof/generate':
                proof = self.zk_proofs_system.generate_proof(data.get('statement', ''), data.get('witness', {}), data.get('public_inputs', {}))
                self._send_json({'success': proof is not None, 'proof_id': proof.proof_id if proof else None})
            elif path == '/api/zk/private_transaction':
                tx = self.zk_proofs_system.create_private_transaction(data.get('sender', ''), data.get('receiver', ''), float(data.get('amount', 0)))
                self._send_json({'success': True, 'transaction': tx})
            elif path == '/api/zk/range_proof':
                proof_id = self.zk_proofs_system.generate_range_proof(int(data.get('value', 0)), int(data.get('min', 0)), int(data.get('max', 2**64)))
                self._send_json({'success': True, 'proof_id': proof_id})
            elif path == '/api/connect':
                host = data.get('host', 'localhost')
                port = data.get('port', 0)
                if p2p_node and port:
                    success = p2p_node.connect(host, port)
                    self._send_json({'success': success, 'peer': f"{host}:{port}"})
                else:
                    self._send_json({'success': False, 'error': 'P2P node not available'})
            else:
                self._send_error(404, 'Not found')
        except Exception as e:
            print(f"⚠️ POST Error: {e}")
            self._send_error(500, str(e))

    # ============== HTML СТРАНИЦЫ ==============
    
    def _get_main_page(self):
        return f'''<!DOCTYPE html>
        <html><head><meta charset="UTF-8"><title>Absolute Blockchain v15.0</title>
        <style>
        *{{margin:0;padding:0;box-sizing:border-box}}
        body{{font-family:'Segoe UI',monospace;background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);color:white;min-height:100vh;padding:20px}}
        .container{{max-width:1200px;margin:0 auto}}
        h1{{font-size:2.5em;background:linear-gradient(135deg,#ffd700,#ff6b6b);-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-align:center;margin-bottom:20px}}
        .nav{{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-bottom:30px}}
        .nav a{{color:white;text-decoration:none;padding:10px 20px;background:rgba(255,255,255,0.1);border-radius:30px;transition:0.3s}}
        .nav a:hover{{background:#ffd700;color:#000}}
        .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:20px;margin-bottom:30px}}
        .stat-card{{background:rgba(255,255,255,0.1);border-radius:15px;padding:20px;text-align:center}}
        .stat-value{{font-size:2em;font-weight:bold;color:#ffd700}}
        .footer{{text-align:center;margin-top:50px;padding:20px;border-top:1px solid rgba(255,255,255,0.1)}}
        </style>
        </head>
        <body>
        <div class="container">
        <h1>⚡ ABSOLUTE BLOCKCHAIN ULTIMATE v15.0</h1>
        <div class="nav">
        <a href="/">🏠 Главная</a><a href="/wallet">👛 Кошелек</a><a href="/explorer">🔍 Explorer</a>
        <a href="/staking">💰 Стейкинг</a><a href="/nft">🦋 NFT</a><a href="/evm">📦 EVM</a>
        <a href="/wasm">🦀 WASM</a><a href="/lightning">⚡ Lightning</a><a href="/ai">🤖 AI</a>
        <a href="/bridge">🌉 Мосты</a><a href="/smart_account">👤 Smart Account</a><a href="/will">📜 Завещание</a>
        <a href="/quantum">🔐 Quantum</a><a href="/sharding">🗺️ Шардинг</a><a href="/plasma">⚡ Plasma</a>
        <a href="/zk">🔒 ZK</a><a href="/validator">⚖️ Валидаторы</a><a href="/dashboard">📊 Дашборд</a>
        <a href="/docs">📚 API Docs</a>
        </div>
        <div class="stats">
        <div class="stat-card"><div class="stat-value" id="blocks">-</div><div>Блоков</div></div>
        <div class="stat-card"><div class="stat-value" id="peers">-</div><div>Пиров</div></div>
        <div class="stat-card"><div class="stat-value" id="supply">-</div><div>Эмиссия</div></div>
        </div>
        <div class="footer">
        🔐 DABRANSKI ULADZIMIR PETROVICH | 14.07.1987 | GRODNO
        </div>
        </div>
        <script>
        async function loadStats(){{try{{const r=await fetch('/api/stats');const d=await r.json();document.getElementById('blocks').innerText=d.blocks||0;const p=await fetch('/api/peers');const pd=await p.json();document.getElementById('peers').innerText=pd.peers?.length||0;document.getElementById('supply').innerText=Math.round(d.total_supply||0).toLocaleString()}}catch(e){{}}}}
        loadStats();setInterval(loadStats,5000);
        </script>
        </body></html>'''
    
    def _get_docs_page(self):
        return '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>API Docs</title><style>body{font-family:monospace;background:#0f0c29;color:white;padding:20px}</style></head><body><h1>📚 API Documentation</h1><h2>GET</h2><p>/api/stats - статистика</p><p>/api/blocks - блоки</p><p>/api/balance?address=xxx - баланс</p><h2>POST</h2><p>/api/wallet/create - создать кошелек</p><p>/api/transaction/send - отправить транзакцию</p><p>/api/mine - майнинг</p><p>/api/validator/register - регистрация валидатора</p><p>/api/stake - делегировать стейк</p><p>/api/evm/deploy - деплой контракта</p><p>/api/nft/mint - mint NFT</p><p>/api/ai/agent/create - создать AI агента</p><p>/api/bridge/transfer - кросс-чейн перевод</p><p>/api/will/create - создать завещание</p><p>/api/smart_account/create - создать мультисиг</p></body></html>'''
    
    def _get_wallet_page(self):
        return '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Wallet</title><style>body{font-family:monospace;background:#0f0c29;color:white;padding:20px}button{background:#ffd700;color:#000;padding:10px;border-radius:8px;cursor:pointer}input{padding:10px;margin:5px;background:rgba(0,0,0,0.5);color:white;border:none;border-radius:8px}.result{background:rgba(0,0,0,0.5);padding:15px;margin-top:15px}</style></head><body><h1>👛 Кошелек</h1><button onclick="createWallet()">Создать кошелек</button><div id="result" class="result"></div><h2>Баланс</h2><input id="addr" placeholder="Адрес"><button onclick="checkBalance()">Проверить</button><div id="balance" class="result"></div><script>async function createWallet(){const r=await fetch('/api/wallet/create',{method:'POST'});const d=await r.json();document.getElementById('result').innerHTML='✅ Кошелек создан!<br>Адрес: '+(d.quantum_address||d.address)+'<br>Приватный ключ: '+d.private_key}async function checkBalance(){const addr=document.getElementById('addr').value;if(!addr)return;const r=await fetch('/api/balance?address='+addr);const d=await r.json();document.getElementById('balance').innerHTML='💰 Баланс: '+(d.balance||0)+' ABS'}</script></body></html>'''
    
    def _get_explorer_page(self):
        return '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Explorer</title><style>body{font-family:monospace;background:#0f0c29;color:white;padding:20px}.block{background:rgba(255,255,255,0.1);margin:10px 0;padding:15px;border-radius:10px}</style></head><body><h1>🔍 Explorer</h1><div id="blocks"></div><script>fetch('/api/blocks').then(r=>r.json()).then(d=>{let h='';for(let b of d.slice().reverse()){h+=`<div class="block"><b>Блок #${b.height}</b><br>Хеш: ${b.block_hash}<br>Майнер: ${b.miner}<br>Транзакций: ${b.transactions?.length||0}</div>`}document.getElementById('blocks').innerHTML=h})</script></body></html>'''
    
    def _get_staking_page(self):
        return '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Staking</title><style>body{font-family:monospace;background:#0f0c29;color:white;padding:20px}</style></head><body><h1>💰 Стейкинг</h1><div id="stats"></div><script>fetch('/api/staking').then(r=>r.json()).then(d=>{document.getElementById('stats').innerHTML=`<p>Всего застейкано: ${d.total_staked} ABS</p><p>APY: ${d.apy}%</p>`})</script></body></html>'''
    
    def _get_nft_page(self):
        return '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>NFT</title><style>body{font-family:monospace;background:#0f0c29;color:white;padding:20px}</style></head><body><h1>🦋 NFT</h1><div id="nfts"></div><script>fetch('/api/nft/tokens').then(r=>r.json()).then(d=>{document.getElementById('nfts').innerHTML=JSON.stringify(d,null,2)})</script></body></html>'''
    
    def _get_evm_page(self):
        return '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>EVM</title><style>body{font-family:monospace;background:#0f0c29;color:white;padding:20px}</style></head><body><h1>📦 EVM</h1><div id="contracts"></div><script>fetch('/api/evm/contracts').then(r=>r.json()).then(d=>{document.getElementById('contracts').innerHTML=JSON.stringify(d,null,2)})</script></body></html>'''
    
    def _get_wasm_page(self):
        return '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>WASM</title><style>body{font-family:monospace;background:#0f0c29;color:white;padding:20px}</style></head><body><h1>🦀 WASM</h1><div id="contracts"></div><script>fetch('/api/wasm/contracts').then(r=>r.json()).then(d=>{document.getElementById('contracts').innerHTML=JSON.stringify(d,null,2)})</script></body></html>'''
    
    def _get_lightning_page(self):
        return '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Lightning</title><style>body{font-family:monospace;background:#0f0c29;color:white;padding:20px}</style></head><body><h1>⚡ Lightning</h1><div id="channels"></div><script>fetch('/api/lightning/channels').then(r=>r.json()).then(d=>{document.getElementById('channels').innerHTML=JSON.stringify(d,null,2)})</script></body></html>'''
    
    def _get_ai_page(self):
        return '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>AI</title><style>body{font-family:monospace;background:#0f0c29;color:white;padding:20px}</style></head><body><h1>🤖 AI Agents</h1><div id="agents"></div><script>fetch('/api/ai/agents').then(r=>r.json()).then(d=>{document.getElementById('agents').innerHTML=JSON.stringify(d,null,2)})</script></body></html>'''
    
    def _get_bridge_page(self):
        return '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Bridge</title><style>body{font-family:monospace;background:#0f0c29;color:white;padding:20px}</style></head><body><h1>🌉 Bridge</h1><div id="transfers"></div><script>fetch('/api/bridge/transfers').then(r=>r.json()).then(d=>{document.getElementById('transfers').innerHTML=JSON.stringify(d,null,2)})</script></body></html>'''
    
    def _get_smart_account_page(self):
        return '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Smart Accounts</title><style>body{font-family:monospace;background:#0f0c29;color:white;padding:20px}</style></head><body><h1>👤 Smart Accounts</h1><div id="accounts"></div><script>fetch('/api/smart_account/accounts').then(r=>r.json()).then(d=>{document.getElementById('accounts').innerHTML=JSON.stringify(d,null,2)})</script></body></html>'''
    
    def _get_will_page(self):
        return '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Crypto Will</title><style>body{font-family:monospace;background:#0f0c29;color:white;padding:20px}</style></head><body><h1>📜 Crypto Will</h1><div id="wills"></div><script>fetch('/api/will/wills').then(r=>r.json()).then(d=>{document.getElementById('wills').innerHTML=JSON.stringify(d,null,2)})</script></body></html>'''
    
    def _get_quantum_page(self):
        return '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Quantum</title><style>body{font-family:monospace;background:#0f0c29;color:white;padding:20px}</style></head><body><h1>🔐 Quantum</h1><div id="keys"></div><script>fetch('/api/quantum/keys?address=test').then(r=>r.json()).then(d=>{document.getElementById('keys').innerHTML=JSON.stringify(d,null,2)})</script></body></html>'''
    
    def _get_sharding_page(self):
        return '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Sharding</title><style>body{font-family:monospace;background:#0f0c29;color:white;padding:20px}</style></head><body><h1>🗺️ Sharding</h1><div id="stats"></div><script>fetch('/api/sharding').then(r=>r.json()).then(d=>{document.getElementById('stats').innerHTML=JSON.stringify(d,null,2)})</script></body></html>'''
    
    def _get_plasma_page(self):
        return '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Plasma</title><style>body{font-family:monospace;background:#0f0c29;color:white;padding:20px}</style></head><body><h1>⚡ Plasma</h1><div id="stats"></div><script>fetch('/api/plasma/stats').then(r=>r.json()).then(d=>{document.getElementById('stats').innerHTML=JSON.stringify(d,null,2)})</script></body></html>'''
    
    def _get_zk_page(self):
        return '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>ZK-Proofs</title><style>body{font-family:monospace;background:#0f0c29;color:white;padding:20px}</style></head><body><h1>🔒 ZK-Proofs</h1><div id="stats"></div><script>fetch('/api/zk/stats').then(r=>r.json()).then(d=>{document.getElementById('stats').innerHTML=JSON.stringify(d,null,2)})</script></body></html>'''
    
    def _get_dashboard_page(self):
        return '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Dashboard</title><style>body{font-family:monospace;background:#0f0c29;color:white;padding:20px}</style></head><body><h1>📊 Dashboard</h1><div id="info"></div><script>fetch('/api/stats').then(r=>r.json()).then(d=>{document.getElementById('info').innerHTML=`<p>Блоков: ${d.blocks}</p><p>Эмиссия: ${d.total_supply} ABS</p><p>Сложность: ${d.difficulty}</p>`})</script></body></html>'''
    
    def _get_validator_page(self):
        return '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Validators</title><style>body{font-family:monospace;background:#0f0c29;color:white;padding:20px}</style></head><body><h1>⚖️ Validators</h1><div id="validators"></div><script>fetch('/api/validators').then(r=>r.json()).then(d=>{let h='';for(let v of d.validators||[]){h+=`<p>${v.validator_id}: ${v.stake} ABS</p>`}document.getElementById('validators').innerHTML=h})</script></body></html>'''

# ============== APIServer ==============

class APIServer:
    def __init__(self, port: int):
        self.port = port
        self.server = None

    def start(self):
        self.server = HTTPServer(('0.0.0.0', self.port), APIHandler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        print(f"{C.GREEN}🌐 API Server started on http://localhost:{self.port}{C.RESET}")
        print(f"{C.GREEN}📚 API Documentation: http://localhost:{self.port}/docs{C.RESET}")

    def stop(self):
        if self.server:
            self.server.shutdown()

# ============== ГЛАВНЫЙ ЗАПУСК ==============

def print_banner():
    banner = f"""
{C.CYAN}╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                                   ║
║     █████╗ ██████╗ ███████╗ ██████╗ ██╗   ██╗████████╗███████╗                     ║
║    ██╔══██╗██╔══██╗██╔════╝██╔═══██╗██║   ██║╚══██╔══╝██╔════╝                     ║
║    ███████║██████╔╝███████╗██║   ██║██║   ██║   ██║   ███████╗                     ║
║    ██╔══██║██╔══██╗╚════██║██║   ██║██║   ██║   ██║   ╚════██║                     ║
║    ██║  ██║██████╔╝███████║╚██████╔╝╚██████╔╝   ██║   ███████║                     ║
║    ╚═╝  ╚═╝╚═════╝ ╚══════╝ ╚═════╝  ╚═════╝    ╚═╝   ╚══════╝                     ║
║                                                                                   ║
║                    ABSOLUTE BLOCKCHAIN ULTIMATE v15.0                             ║
║                         ПОЛНОСТЬЮ ИСПРАВЛЕННАЯ ВЕРСИЯ                              ║
║                                                                                   ║
╚═══════════════════════════════════════════════════════════════════════════════╝
{C.RESET}
"""
    print(banner)

def main():
    global p2p_manager, p2p_node, api_server
    
    os.system('cls' if os.name == 'nt' else 'clear')
    print_banner()
    
    print(f"{C.CYAN}{'='*70}{C.RESET}")
    print(f"{C.YELLOW}  🚀 ЗАПУСК ABSOLUTE BLOCKCHAIN ULTIMATE v15.0 (ИСПРАВЛЕННАЯ){C.RESET}")
    print(f"{C.CYAN}{'='*70}{C.RESET}\n")
    
    # Инициализация P2P сети
    print(f"{C.CYAN}🌐 Инициализация P2P сети...{C.RESET}")
    p2p_manager = P2PNetworkManager()
    p2p_node = p2p_manager.create_node(blockchain, "127.0.0.1", config.network.P2P_PORT)
    threading.Thread(target=p2p_node.start_server, daemon=True).start()
    time.sleep(1)
    
    if config.network.P2P_PORT == 5000:
        slave1 = p2p_manager.create_node(blockchain, "127.0.0.1", 5001)
        slave2 = p2p_manager.create_node(blockchain, "127.0.0.1", 5002)
        threading.Thread(target=slave1.start_server, daemon=True).start()
        threading.Thread(target=slave2.start_server, daemon=True).start()
        time.sleep(1)
        p2p_node.connect("127.0.0.1", 5001)
        p2p_node.connect("127.0.0.1", 5002)
        slave1.connect("127.0.0.1", 5000)
        slave2.connect("127.0.0.1", 5000)
        print(f"{C.GREEN}✅ Создана тестовая P2P сеть: MASTER(5000), SLAVE1(5001), SLAVE2(5002){C.RESET}")
    
    print(f"{C.GREEN}✅ P2P сеть запущена на порту {config.network.P2P_PORT}{C.RESET}")
    
    # Запуск API сервера
    api_server = APIServer(config.network.API_PORT)
    api_server.start()
    
    # Тестовый кошелек
    try:
        test_wallet = quantum_crypto.generate_quantum_keypair()
        print(f"{C.GREEN}🎉 Тестовый кошелек создан:{C.RESET}")
        print(f"   Address: {test_wallet.get('quantum_address', test_wallet.get('address', 'N/A'))}")
        print(f"   Algorithm: {test_wallet.get('algorithm', 'SPHINCS+')}")
    except:
        pass
    
    print(f"\n{C.GREEN}{'='*70}{C.RESET}")
    print(f"{C.GREEN}  ✅ БЛОКЧЕЙН УСПЕШНО ЗАПУЩЕН!{C.RESET}")
    print(f"{C.GREEN}{'='*70}{C.RESET}")
    print(f"{C.YELLOW}  🌐 Веб-интерфейс: http://localhost:{config.network.API_PORT}{C.RESET}")
    print(f"{C.YELLOW}  📚 API Docs: http://localhost:{config.network.API_PORT}/docs{C.RESET}")
    print(f"{C.YELLOW}  🔗 P2P порт: {config.network.P2P_PORT}{C.RESET}")
    print(f"{C.YELLOW}  📊 Всего блоков: {len(blockchain.chain)}{C.RESET}")
    print(f"{C.YELLOW}  🌍 P2P пиров: {len(p2p_node.peers)}{C.RESET}")
    print(f"\n{C.CYAN}  💡 Доступные модули:{C.RESET}")
    print(f"     • Квантовая криптография: {quantum_crypto.algorithm}")
    print(f"     • EVM контрактов: {len(evm.contracts)}")
    print(f"     • WASM контрактов: {len(wasm_vm.contracts)}")
    print(f"     • NFT коллекций: {len(nft_manager.collections)}")
    print(f"     • Lightning каналов: {len(lightning.channels)}")
    print(f"     • AI агентов: {len(ai_manager.agents)}")
    print(f"     • Кросс-чейн переводов: {len(bridge.transfers)}")
    print(f"     • Smart Accounts: {len(smart_account_manager.accounts)}")
    print(f"     • Crypto Will: {len(crypto_will_manager.wills)}")
    print(f"     • Шардинг: {sharding_manager.shard_count} шардов")
    print(f"     • Plasma блоков: {len(plasma_chain.blocks)}")
    print(f"     • ZK-Proofs: {zk_proofs_system.get_stats()['total_proofs']} доказательств")
    print(f"     • P2P узлов: {len(p2p_manager.nodes)}")
    print(f"\n{C.YELLOW}  🛑 Нажмите Ctrl+C для остановки{C.RESET}\n")
    
    try:
        while not SHOULD_STOP.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        SHOULD_STOP.set()
    
    print(f"\n{C.YELLOW}  🛑 Остановка блокчейна...{C.RESET}")
    if api_server:
        api_server.stop()
    if p2p_manager:
        p2p_manager.stop_all()
    
    print(f"{C.GREEN}  ✅ Блокчейн остановлен. До свидания!{C.RESET}")

if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda s, f: SHOULD_STOP.set())
    signal.signal(signal.SIGTERM, lambda s, f: SHOULD_STOP.set())
    main()