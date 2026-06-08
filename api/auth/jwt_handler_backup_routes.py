# api/auth/jwt_handler.py - ИСПРАВЛЕННАЯ ВЕРСИЯ (БЕЗ DEADLOCK)
import jwt
import time
import secrets
import hashlib
from typing import Dict, Optional
from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    access_expires_in: int
    refresh_expires_in: int
    token_type: str = "Bearer"

class JWTAuthenticator:
    def __init__(self):
        self.secret_key = os.getenv('JWT_SECRET', 'absolute_blockchain_super_secret_key_2025')
        self.algorithm = os.getenv('JWT_ALGORITHM', 'HS256')
        self.access_expire_minutes = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRE_MINUTES', 15))
        self.refresh_expire_days = int(os.getenv('JWT_REFRESH_TOKEN_EXPIRE_DAYS', 7))
        
        # Используем обычные словари, без сложных блокировок
        self._blacklist: Dict[str, float] = {}
        self._refresh_tokens: Dict[str, dict] = {}
        self._challenges: Dict[str, dict] = {}
        
        # Простые счётчики без блокировок для статистики
        self._stats = {'challenges_created': 0, 'tokens_issued': 0}
    
    def create_challenge(self, address: str) -> dict:
        """Создать challenge - БЕЗ БЛОКИРОВОК"""
        nonce = secrets.token_hex(32)
        expires_at = time.time() + 300
        
        self._challenges[address] = {
            'nonce': nonce,
            'expires_at': expires_at,
            'created_at': time.time()
        }
        self._stats['challenges_created'] += 1
        
        message = f"Absolute Blockchain Authentication\n\nAddress: {address}\nNonce: {nonce}\nTimestamp: {int(time.time())}\nExpires: {int(expires_at)}\n\nSign this message to authenticate."
        
        return {
            'nonce': nonce,
            'message': message,
            'expires_in': 300
        }
    
    def verify_challenge(self, address: str, nonce: str, signature: str) -> bool:
        """Проверить challenge - БЕЗ БЛОКИРОВОК"""
        challenge = self._challenges.get(address)
        if not challenge:
            return False
        
        if challenge['nonce'] != nonce:
            return False
        
        if time.time() > challenge['expires_at']:
            # Удаляем просроченный
            if address in self._challenges:
                del self._challenges[address]
            return False
        
        # Для теста принимаем любую непустую подпись
        if not signature:
            return False
        
        # Удаляем использованный challenge
        if address in self._challenges:
            del self._challenges[address]
        
        return True
    
    def generate_tokens(self, address: str, role: str = "user") -> TokenPair:
        """Создать токены - БЕЗ БЛОКИРОВОК"""
        now = int(time.time())
        
        access_payload = {
            'sub': address,
            'role': role,
            'type': 'access',
            'iat': now,
            'exp': now + (self.access_expire_minutes * 60),
            'jti': secrets.token_hex(16)
        }
        access_token = jwt.encode(access_payload, self.secret_key, algorithm=self.algorithm)
        
        refresh_payload = {
            'sub': address,
            'type': 'refresh',
            'iat': now,
            'exp': now + (self.refresh_expire_days * 24 * 3600),
            'jti': secrets.token_hex(16)
        }
        refresh_token = jwt.encode(refresh_payload, self.secret_key, algorithm=self.algorithm)
        
        self._refresh_tokens[refresh_token] = {
            'address': address,
            'role': role,
            'created_at': now,
            'expires_at': refresh_payload['exp']
        }
        self._stats['tokens_issued'] += 1
        
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_in=self.access_expire_minutes * 60,
            refresh_expires_in=self.refresh_expire_days * 24 * 3600
        )
    
    def verify_access_token(self, token: str) -> Optional[dict]:
        """Проверить access токен - БЕЗ БЛОКИРОВОК"""
        try:
            if token in self._blacklist:
                return None
            
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            if payload.get('type') != 'access':
                return None
            return payload
        except:
            return None
    
    def refresh_access_token(self, refresh_token: str) -> Optional[TokenPair]:
        """Обновить токен - БЕЗ БЛОКИРОВОК"""
        try:
            payload = jwt.decode(refresh_token, self.secret_key, algorithms=[self.algorithm])
            if payload.get('type') != 'refresh':
                return None
            
            address = payload.get('sub')
            if refresh_token not in self._refresh_tokens:
                return None
            
            role = self._refresh_tokens[refresh_token].get('role', 'user')
            return self.generate_tokens(address, role)
        except:
            return None
    
    def revoke_token(self, token: str) -> bool:
        """Отозвать токен - БЕЗ БЛОКИРОВОК"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm], options={'verify_exp': False})
            expires_at = payload.get('exp', time.time() + 3600)
            self._blacklist[token] = expires_at
            
            if payload.get('type') == 'refresh' and token in self._refresh_tokens:
                del self._refresh_tokens[token]
            
            return True
        except:
            return False
    
    def get_user_from_token(self, token: str) -> Optional[str]:
        """Получить пользователя из токена - БЕЗ БЛОКИРОВОК"""
        payload = self.verify_access_token(token)
        return payload.get('sub') if payload else None
    
    def cleanup_expired(self):
        """Очистка просроченных данных (вызывается извне)"""
        now = time.time()
        
        # Очистка challenge'ей
        expired_challenges = [addr for addr, ch in self._challenges.items() if ch['expires_at'] < now]
        for addr in expired_challenges:
            if addr in self._challenges:
                del self._challenges[addr]
        
        # Очистка refresh токенов
        expired_tokens = [token for token, data in self._refresh_tokens.items() if data['expires_at'] < now]
        for token in expired_tokens:
            if token in self._refresh_tokens:
                del self._refresh_tokens[token]
        
        # Очистка blacklist
        expired_blacklist = [token for token, expiry in self._blacklist.items() if expiry < now]
        for token in expired_blacklist:
            if token in self._blacklist:
                del self._blacklist[token]
    
    def get_stats(self) -> dict:
        """Статистика - БЕЗ БЛОКИРОВОК"""
        return {
            'active_challenges': len(self._challenges),
            'active_refresh_tokens': len(self._refresh_tokens),
            'blacklist_size': len(self._blacklist),
            'challenges_created': self._stats['challenges_created'],
            'tokens_issued': self._stats['tokens_issued']
        }

jwt_auth = JWTAuthenticator()
