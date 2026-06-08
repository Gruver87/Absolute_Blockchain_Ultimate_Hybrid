# core/tx_builder.py - Build and sign transactions
import hashlib
import json
import ecdsa
import base58
from typing import Optional

class TransactionBuilder:
    """Build and sign transactions"""
    
    @staticmethod
    def create_transaction(from_addr: str, to_addr: str, value: int, 
                          nonce: int = 0, gas_price: int = 1, 
                          gas_limit: int = 21000) -> dict:
        """Create unsigned transaction"""
        return {
            'from': from_addr,
            'to': to_addr,
            'value': value,
            'nonce': nonce,
            'gasPrice': gas_price,
            'gasLimit': gas_limit,
            'data': '',
            'chainId': 1337
        }
    
    @staticmethod
    def sign_transaction(tx: dict, private_key: ecdsa.SigningKey) -> dict:
        """Sign transaction with private key"""
        tx_copy = tx.copy()
        tx_string = json.dumps(tx_copy, sort_keys=True)
        signature = private_key.sign(tx_string.encode())
        tx_copy['signature'] = base58.b58encode(signature).decode()
        tx_copy['hash'] = hashlib.sha256(tx_string.encode()).hexdigest()[:16]
        return tx_copy
    
    @staticmethod
    def verify_transaction(tx: dict, public_key: ecdsa.VerifyingKey) -> bool:
        """Verify transaction signature"""
        if 'signature' not in tx:
            return False
        tx_copy = tx.copy()
        signature = base58.b58decode(tx_copy.pop('signature'))
        tx_string = json.dumps(tx_copy, sort_keys=True)
        try:
            return public_key.verify(signature, tx_string.encode())
        except:
            return False
