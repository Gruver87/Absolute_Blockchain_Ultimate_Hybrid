# core/transaction.py
# НАСТОЯЩАЯ ТРАНЗАКЦИЯ С ECDSA ПОДПИСЬЮ

import json
import hashlib
import time
from typing import Dict, Optional
from dataclasses import dataclass, field
from crypto.wallet import Wallet

# Типы транзакций
TX_TRANSFER = "transfer"
TX_STAKE = "stake"
TX_UNSTAKE = "unstake"
TX_GENESIS = "genesis"
TX_COINBASE = "coinbase"

@dataclass
class Transaction:
    """Полноценная транзакция с ECDSA подписью"""
    from_addr: str
    to_addr: str
    amount: float
    timestamp: int = field(default_factory=lambda: int(time.time()))
    signature: str = ""
    public_key: str = ""
    tx_hash: str = ""
    tx_type: str = TX_TRANSFER
    nonce: int = 0
    fee: float = 0.001
    
    def calculate_hash(self) -> str:
        """Вычисление хеша транзакции"""
        data = {
            "from": self.from_addr,
            "to": self.to_addr,
            "amount": self.amount,
            "timestamp": self.timestamp,
            "tx_type": self.tx_type,
            "nonce": self.nonce,
            "fee": self.fee
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    
    def sign(self, private_key_hex: str):
        """Подписание транзакции"""
        self.tx_hash = self.calculate_hash()
        signature, public_key = Wallet.sign_message(private_key_hex, self.tx_hash)
        self.signature = signature
        self.public_key = public_key
    
    def verify(self) -> bool:
        """Проверка подписи транзакции"""
        if self.from_addr == "SYSTEM":
            return True
        
        if not self.signature or not self.public_key:
            return False
        
        tx_hash = self.calculate_hash()
        return Wallet.verify_signature(self.public_key, tx_hash, self.signature)
    
    def to_dict(self) -> Dict:
        """Сериализация"""
        return {
            "tx_hash": self.tx_hash,
            "from_addr": self.from_addr,
            "to_addr": self.to_addr,
            "amount": self.amount,
            "timestamp": self.timestamp,
            "signature": self.signature,
            "public_key": self.public_key,
            "tx_type": self.tx_type,
            "nonce": self.nonce,
            "fee": self.fee
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Transaction':
        """Десериализация"""
        return cls(
            from_addr=data.get('from_addr', ''),
            to_addr=data.get('to_addr', ''),
            amount=float(data.get('amount', 0)),
            timestamp=data.get('timestamp', int(time.time())),
            signature=data.get('signature', ''),
            public_key=data.get('public_key', ''),
            tx_hash=data.get('tx_hash', ''),
            tx_type=data.get('tx_type', TX_TRANSFER),
            nonce=data.get('nonce', 0),
            fee=data.get('fee', 0.001)
        )
    
    @classmethod
    def create_transfer(cls, from_addr: str, to_addr: str, amount: float,
                        private_key: str, nonce: int = 0) -> 'Transaction':
        """Создание transfer транзакции"""
        tx = cls(
            from_addr=from_addr,
            to_addr=to_addr,
            amount=amount,
            tx_type=TX_TRANSFER,
            nonce=nonce
        )
        tx.sign(private_key)
        return tx
    
    @classmethod
    def create_genesis(cls, to_addr: str = "foundation", amount: float = 1000000000.0) -> 'Transaction':
        """Создание genesis транзакции"""
        tx = cls(
            from_addr="SYSTEM",
            to_addr=to_addr,
            amount=amount,
            tx_type=TX_GENESIS,
            nonce=0,
            fee=0
        )
        tx.tx_hash = tx.calculate_hash()
        return tx
    
    @classmethod
    def create_coinbase(cls, miner: str, amount: float) -> 'Transaction':
        """Создание coinbase транзакции (награда майнеру)"""
        tx = cls(
            from_addr="SYSTEM",
            to_addr=miner,
            amount=amount,
            tx_type=TX_COINBASE,
            nonce=0,
            fee=0
        )
        tx.tx_hash = tx.calculate_hash()
        return tx

# Тест
if __name__ == "__main__":
    print("=" * 60)
    print("Transaction - Тест")
    print("=" * 60)
    
    from crypto.wallet import Wallet
    
    wallet = Wallet.create_wallet()
    print(f"\n👛 Кошелёк: {wallet['address']}")
    
    tx = Transaction.create_transfer(
        from_addr=wallet['address'],
        to_addr="receiver",
        amount=100.0,
        private_key=wallet['private_key'],
        nonce=1
    )
    
    print(f"📦 Транзакция: {tx.tx_hash[:32]}...")
    print(f"   Подпись: {tx.signature[:32]}...")
    print(f"   Верификация: {tx.verify()}")
    
    print("\n✅ Transaction готов!")
