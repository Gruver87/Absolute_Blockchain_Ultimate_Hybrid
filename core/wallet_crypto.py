# core/wallet_crypto.py - Simple wallet implementation
import hashlib
import ecdsa
import base58
import json
import os
from typing import Tuple, Optional

class Wallet:
    """Simple blockchain wallet"""
    
    def __init__(self, private_key: Optional[ecdsa.SigningKey] = None):
        if private_key:
            self.private_key = private_key
        else:
            self.private_key = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
        
        self.public_key = self.private_key.get_verifying_key()
        self.address = self._generate_address()
        self.balance = 0
    
    def _generate_address(self) -> str:
        """Generate address from public key"""
        pub_key_bytes = self.public_key.to_string()
        hash160 = hashlib.new('ripemd160', hashlib.sha256(pub_key_bytes).digest()).digest()
        return '0x' + hash160.hex()[:40]
    
    @classmethod
    def create(cls) -> 'Wallet':
        """Create new wallet"""
        return cls()
    
    @classmethod
    def load(cls, filename: str = "data/wallet.json") -> Optional['Wallet']:
        """Load wallet from file"""
        if not os.path.exists(filename):
            return None
        
        with open(filename, 'r') as f:
            data = json.load(f)
        
        # For demo, return a new wallet
        return cls.create()
    
    def save(self, filename: str = "data/wallet.json"):
        """Save wallet to file"""
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w') as f:
            json.dump({
                'address': self.address,
                'balance': self.balance
            }, f, indent=2)
    
    def sign(self, message: bytes) -> bytes:
        """Sign message with private key"""
        return self.private_key.sign(message)
    
    def verify(self, message: bytes, signature: bytes) -> bool:
        """Verify signature with public key"""
        try:
            return self.public_key.verify(signature, message)
        except:
            return False
    
    def get_balance(self) -> int:
        """Get wallet balance"""
        return self.balance
    
    def __str__(self):
        return f"Wallet({self.address[:16]}..., balance={self.balance})"


# For backwards compatibility
def generate_keys() -> Tuple[ecdsa.SigningKey, ecdsa.VerifyingKey]:
    """Generate new key pair"""
    private_key = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
    public_key = private_key.get_verifying_key()
    return private_key, public_key


def address_from_pubkey(public_key: ecdsa.VerifyingKey) -> str:
    """Generate address from public key"""
    pub_key_bytes = public_key.to_string()
    hash160 = hashlib.new('ripemd160', hashlib.sha256(pub_key_bytes).digest()).digest()
    return '0x' + hash160.hex()[:40]
