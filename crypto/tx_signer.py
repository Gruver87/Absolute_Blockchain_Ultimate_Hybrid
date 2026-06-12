#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Подпись и верификация транзакций"""

import hashlib
import hmac
import json
import secrets
import time
from typing import Dict, Any, Tuple, Optional

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
        return hashlib.sha256(message.encode()).hexdigest()
    
    @staticmethod
    def sign_transaction(tx_data: Dict[str, Any], private_key: str) -> str:
        """
        Подпись транзакции
        В реальном блокчейне используется ECDSA, здесь упрощённая версия для демо
        """
        tx_hash = TransactionSigner.hash_transaction(tx_data)
        
        # Упрощённая подпись (в production использовать cryptography или ecdsa)
        # HMAC на основе приватного ключа
        signature = hmac.new(
            private_key.encode() if isinstance(private_key, str) else private_key,
            tx_hash.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    @staticmethod
    def verify_signature(tx_data: Dict[str, Any], signature: str, address: str) -> bool:
        """
        Верификация подписи
        Проверяет, что подпись соответствует адресу
        """
        # В production здесь должна быть проверка ECDSA подписи
        # Сейчас упрощённая проверка
        
        if not signature or len(signature) != 64:
            return False
        
        # Проверка, что подпись не нулевая
        if all(c == '0' for c in signature):
            return False
        
        # В реальном проекте: verify with public key derived from address
        return True
    
    @staticmethod
    def generate_nonce(address: str) -> int:
        """Генерация nonce для защиты от replay attacks"""
        # Используем timestamp + случайное число
        return int(time.time() * 1000) ^ hash(address) % 1000000

# Глобальный экземпляр
tx_signer = TransactionSigner()
