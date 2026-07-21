#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Подпись и верификация транзакций"""

import hashlib
import json
import time
from typing import Dict, Any

from crypto import native
from crypto.keys import KeyGenerator
from crypto.secp256k1_backend import CRYPTO_AVAILABLE, sign, verify

class TransactionSigner:
    """Управление подписями транзакций"""
    
    @staticmethod
    def hash_transaction(tx_data: Dict[str, Any]) -> str:
        """Вычисление хэша транзакции для подписи"""
        # Сортируем поля для детерминированности
        ordered = {
            'from': tx_data.get('from', ''),
            'to': tx_data.get('to', ''),
            'amount': str(tx_data.get('amount', 0)),
            'nonce': str(tx_data.get('nonce', 0)),
            'fee': str(tx_data.get('fee', 0.001))
        }
        
        message = json.dumps(ordered, sort_keys=True)
        return native.sha256_hex(message.encode())
    
    @staticmethod
    def sign_transaction(tx_data: Dict[str, Any], private_key: str) -> str:
        """Подпись транзакции через SECP256K1."""
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("SECP256K1 backend not available")
        tx_hash = TransactionSigner.hash_transaction(tx_data)
        private_key_bytes = bytes.fromhex(private_key) if isinstance(private_key, str) else private_key
        return sign(tx_hash.encode(), private_key_bytes, hashfunc=hashlib.sha256).hex()
    
    @staticmethod
    def verify_signature(tx_data: Dict[str, Any], signature: str, address: str) -> bool:
        """
        Верификация подписи
        Проверяет, что подпись соответствует public_key и адресу.
        """
        if not CRYPTO_AVAILABLE:
            return False
        if not signature:
            return False
        public_key_hex = tx_data.get("public_key", "")
        if not public_key_hex:
            return False
        try:
            public_key = bytes.fromhex(public_key_hex)
            signature_bytes = bytes.fromhex(signature)
        except ValueError:
            return False
        if address:
            derived = KeyGenerator.derive_address(public_key)
            if derived.lower() != address.lower():
                return False
        tx_hash = TransactionSigner.hash_transaction(tx_data)
        return verify(tx_hash.encode(), signature_bytes, public_key, hashfunc=hashlib.sha256)
    
    @staticmethod
    def generate_nonce(address: str) -> int:
        """Генерация nonce для защиты от replay attacks"""
        # Используем timestamp + случайное число
        return int(time.time() * 1000) ^ hash(address) % 1000000

# Глобальный экземпляр
tx_signer = TransactionSigner()
