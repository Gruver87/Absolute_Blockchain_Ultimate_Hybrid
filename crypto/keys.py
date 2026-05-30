# crypto/keys.py
"""
Cryptographic key generation and management
secp256k1 curve (same as Bitcoin/Ethereum)
"""

import hashlib
import secrets
import base58
from typing import Tuple, Optional
from dataclasses import dataclass

try:
    from ecdsa import SigningKey, VerifyingKey, SECP256k1
    ECDSA_AVAILABLE = True
except ImportError:
    ECDSA_AVAILABLE = False
    print("⚠️ ecdsa not installed. Run: pip install ecdsa")


@dataclass
class KeyPair:
    """Key pair for blockchain identity"""
    private_key: bytes
    public_key: bytes
    address: str
    
    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "public_key": self.public_key.hex(),
            "private_key": self.private_key.hex()  # ⚠️ Only for export!
        }


class KeyGenerator:
    """Generate secp256k1 key pairs"""
    
    @staticmethod
    def generate_private_key() -> bytes:
        """Generate random private key"""
        if ECDSA_AVAILABLE:
            sk = SigningKey.generate(curve=SECP256k1)
            return sk.to_string()
        else:
            # Fallback: secure random
            return secrets.token_bytes(32)
    
    @staticmethod
    def private_to_public(private_key: bytes) -> bytes:
        """Derive public key from private key"""
        if ECDSA_AVAILABLE:
            sk = SigningKey.from_string(private_key, curve=SECP256k1)
            vk = sk.verifying_key
            return vk.to_string()
        else:
            # Simplified fallback (not secure!)
            return hashlib.sha256(private_key).digest()
    
    @staticmethod
    def derive_address(public_key: bytes) -> str:
        """Derive Ethereum-style address from public key"""
        # Hash public key
        sha = hashlib.sha256(public_key).digest()
        # Take last 20 bytes for address
        address_bytes = sha[-20:]
        # Add 0x prefix
        return "0x" + address_bytes.hex()
    
    @staticmethod
    def generate_keypair() -> KeyPair:
        """Generate complete key pair"""
        private_key = KeyGenerator.generate_private_key()
        public_key = KeyGenerator.private_to_public(private_key)
        address = KeyGenerator.derive_address(public_key)
        
        return KeyPair(
            private_key=private_key,
            public_key=public_key,
            address=address
        )
    
    @staticmethod
    def from_private_key(private_key_hex: str) -> KeyPair:
        """Recover key pair from private key hex"""
        private_key = bytes.fromhex(private_key_hex)
        public_key = KeyGenerator.private_to_public(private_key)
        address = KeyGenerator.derive_address(public_key)
        
        return KeyPair(
            private_key=private_key,
            public_key=public_key,
            address=address
        )


# Test vector
if __name__ == "__main__":
    # Generate a test key
    keypair = KeyGenerator.generate_keypair()
    print(f"Address: {keypair.address}")
    print(f"Public Key: {keypair.public_key.hex()[:64]}...")
    print(f"Private Key: {keypair.private_key.hex()[:32]}...")
