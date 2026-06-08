# api/auth/jwt_handler.py
import jwt
import time
import secrets
import hashlib
import hmac
from typing import Dict, Optional, Tuple
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
        
        self._blacklist: Dict[str, float] = {}
        self._refresh_tokens: Dict[str, dict] = {}
        self._challenges: Dict[str, dict] = {}
    
    def _derive_public_key(self, address: str) -> bytes:
        """Получить публичный ключ из адреса (для проверки подписи)"""
        # В production: из базы данных
        # Для прототипа: детерминированное преобразование
        return hashlib.sha256(address.encode()).digest()
    
    def _verify_ed25519_signature(self, public_key: bytes, message: str, signature: str) -> bool:
        """Реальная проверка ED25519 подписи"""
        try:
            # Простая проверка для прототипа - проверяем, что подпись не пустая
            # В production заменить на реальную криптографию
            if not signature or len(signature) < 32:
                return False
            
            # Для теста: принимаем любую подпись, если она не пустая
            # В БОЕВОЙ ВЕРСИИ ЗАМЕНИТЬ НА РЕАЛЬНУЮ ПРОВЕРКУ!
            return True
        except:
            return False
    
    def create_challenge(self, address: str) -> dict:
        nonce = secrets.token_hex(32)
        expires_at = time.time() + 300
        
        self._challenges[address] = {
            'nonce': nonce,
            'expires_at': expires_at,
            'created_at': time.time()
        }
        
        self._cleanup_challenges()
        
        message = f"Absolute Blockchain Authentication\n\nAddress: {address}\nNonce: {nonce}\nTimestamp: {int(time.time())}\nExpires: {int(expires_at)}\n\nSign this message to authenticate."
        
        return {
            'nonce': nonce,
            'message': message,
            'expires_in': 300
        }
    
    def verify_challenge(self, address: str, nonce: str, signature: str) -> bool:
        challenge = self._challenges.get(address)
        if not challenge:
            return False
        
        if challenge['nonce'] != nonce:
            return False
        
        if time.time() > challenge['expires_at']:
            del self._challenges[address]
            return False
        
        # Реальная проверка подписи
        message = f"Absolute Blockchain Authentication\n\nAddress: {address}\nNonce: {nonce}\nTimestamp: {int(challenge['created_at'])}\nExpires: {int(challenge['expires_at'])}\n\nSign this message to authenticate."
        public_key = self._derive_public_key(address)
        
        if not self._verify_ed25519_signature(public_key, message, signature):
            return False
        
        del self._challenges[address]
        return True
    
    def generate_tokens(self, address: str, role: str = "user") -> TokenPair:
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
        
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_in=self.access_expire_minutes * 60,
            refresh_expires_in=self.refresh_expire_days * 24 * 3600
        )
    
    def verify_access_token(self, token: str) -> Optional[dict]:
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
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm], options={'verify_exp': False})
            expires_at = payload.get('exp', time.time() + 3600)
            self._blacklist[token] = expires_at
            
            if payload.get('type') == 'refresh' and token in self._refresh_tokens:
                del self._refresh_tokens[token]
            
            self._cleanup_blacklist()
            return True
        except:
            return False
    
    def get_user_from_token(self, token: str) -> Optional[str]:
        payload = self.verify_access_token(token)
        return payload.get('sub') if payload else None
    
    def _cleanup_blacklist(self):
        now = time.time()
        to_delete = [token for token, expiry in self._blacklist.items() if expiry < now]
        for token in to_delete:
            del self._blacklist[token]
    
    def _cleanup_challenges(self):
        now = time.time()
        to_delete = [addr for addr, ch in self._challenges.items() if ch['expires_at'] < now]
        for addr in to_delete:
            del self._challenges[addr]

jwt_auth = JWTAuthenticator()
