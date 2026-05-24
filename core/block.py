# core/block.py
import time
import hashlib
import json
from dataclasses import dataclass
from core.merkle import MerkleTree

@dataclass
class Block:
    height: int
    previous_hash: str
    transactions: list
    timestamp: int
    nonce: int
    miner: str
    difficulty: int = 1
    merkle_root: str = ""
    block_hash: str = ""
    
    def __post_init__(self):
        if not self.merkle_root and self.transactions:
            self.merkle_root = MerkleTree.build_merkle_root(self.transactions)
    
    def calculate_hash(self):
        block_string = json.dumps({
            'height': self.height,
            'previous_hash': self.previous_hash,
            'timestamp': self.timestamp,
            'merkle_root': self.merkle_root,
            'nonce': self.nonce,
            'miner': self.miner,
            'difficulty': self.difficulty
        }, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()
    
    def calculate_merkle_root(self):
        return MerkleTree.build_merkle_root(self.transactions)
    
    def verify(self):
        if self.transactions and self.calculate_merkle_root() != self.merkle_root:
            return False
        if self.calculate_hash() != self.block_hash:
            return False
        return True
    
    def to_dict(self):
        return {
            'height': self.height,
            'previous_hash': self.previous_hash,
            'merkle_root': self.merkle_root,
            'block_hash': self.block_hash,
            'timestamp': self.timestamp,
            'nonce': self.nonce,
            'miner': self.miner,
            'difficulty': self.difficulty,
            'transactions': [tx.to_dict() for tx in self.transactions]
        }
    
    @staticmethod
    def from_dict(data):
        from core.transaction_utxo import UTXOTransaction
        transactions = [UTXOTransaction.from_dict(tx) for tx in data.get('transactions', [])]
        return Block(
            height=data['height'],
            previous_hash=data['previous_hash'],
            transactions=transactions,
            timestamp=data['timestamp'],
            nonce=data.get('nonce', 0),
            miner=data.get('miner', ''),
            difficulty=data.get('difficulty', 1),
            merkle_root=data.get('merkle_root', ''),
            block_hash=data.get('block_hash', '')
        )
    
    @classmethod
    def genesis(cls):
        from core.tx_builder import TransactionBuilder
        genesis_tx = TransactionBuilder.create_genesis_tx("foundation")
        block = cls(
            height=0,
            previous_hash="0"*64,
            transactions=[genesis_tx],
            timestamp=int(time.time()),
            nonce=0,
            miner="genesis",
            difficulty=1
        )
        block.block_hash = block.calculate_hash()
        return block
