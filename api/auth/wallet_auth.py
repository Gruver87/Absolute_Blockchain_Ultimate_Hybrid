# api/auth/wallet_auth.py
# Challenge-response аутентификация через подпись кошелька

import secrets
import time
import hashlib
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

@dataclass
class AuthChallenge:
    """Вызов для подписи"""
    nonce: str
    address: str
    created_at: float
    expires_at: float
    
    def to_message(self) -> str:
        """Формирует сообщение для подписи"""
        return f"Absolute Blockchain Login\nAddress: {self.address}\nNonce: {self.nonce}\nExpires: {self.expires_at}\nTimestamp: {self.created_at}"
    
    def to_dict(self) -> dict:
        return {
            'nonce': self.nonce,
            'address': self.address,
            'message': self.to_message(),
            'expires_in': int(self.expires_at - time.time())
        }

class WalletAuthenticator:
    """
    Аутентификация через подпись кошелька
    Правильный challenge-response flow
    """
    
    def __init__(self, challenge_ttl_seconds: int = 300):
        self.challenges: Dict[str, AuthChallenge] = {}
        self.challenge_ttl = challenge_ttl_seconds
        self._cleanup_count = 0
    
    def create_challenge(self, address: str) -> AuthChallenge:
        """Создать challenge для подписи"""
        self._cleanup_old_challenges()
        
        nonce = secrets.token_hex(32)
        now = time.time()
        
        challenge = AuthChallenge(
            nonce=nonce,
            address=address,
            created_at=now,
            expires_at=now + self.challenge_ttl
        )
        
        self.challenges[address] = challenge
        return challenge
    
    def verify_signature(self, address: str, signature: str, message: str) -> bool:
        """
        Проверить подпись кошелька
        В production здесь должна быть реальная криптографическая проверка
        """
        # Правильная проверка должна использовать:
        # - ed25519.verify(public_key, message, signature)
        # - secp256k1.verify(public_key, message, signature)
        
        # Для прототипа используем HMAC
        expected = hashlib.sha256(f"{address}{message}".encode()).hexdigest()
        return secrets.compare_digest(signature, expected)
    
    def authenticate(self, address: str, signature: str) -> Tuple[bool, Optional[str]]:
        """
        Аутентифицировать пользователя по подписи
        Возвращает: (успех, сообщение/токен)
        """
        # Проверяем существование challenge
        challenge = self.challenges.get(address)
        if not challenge:
            return False, "No active challenge. Request /api/auth/challenge first"
        
        # Проверяем срок действия
        if time.time() > challenge.expires_at:
            del self.challenges[address]
            return False, "Challenge expired. Request a new one"
        
        # Проверяем подпись
        message = challenge.to_message()
        if not self.verify_signature(address, signature, message):
            return False, "Invalid signature. Authentication failed"
        
        # Успешно! Удаляем использованный challenge
        del self.challenges[address]
        return True, challenge.nonce
    
    def _cleanup_old_challenges(self):
        """Очистить просроченные challenge'и"""
        self._cleanup_count += 1
        if self._cleanup_count % 100 != 0:
            return
        
        now = time.time()
        to_remove = [addr for addr, ch in self.challenges.items() 
                     if now > ch.expires_at]
        for addr in to_remove:
            del self.challenges[addr]
    
    def get_stats(self) -> dict:
        """Статистика аутентификации"""
        return {
            'active_challenges': len(self.challenges),
            'challenge_ttl': self.challenge_ttl
        }

# Глобальный экземпляр
wallet_auth = WalletAuthenticator()
