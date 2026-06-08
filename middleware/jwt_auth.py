# middleware/jwt_auth.py
import jwt
import secrets
import time
import os
from typing import Dict, Optional, Tuple
from functools import wraps

# Секретный ключ из переменных окружения
SECRET_KEY = os.getenv("JWT_SECRET", secrets.token_hex(32))
ALGORITHM = "HS256"

class JWTAuth:
    """JWT авторизация"""
    
    def __init__(self):
        self.secret_key = SECRET_KEY
        self.expiration_hours = 24
        self.blacklist = set()
    
    def generate_token(self, address: str, role: str = "user") -> str:
        payload = {
            'address': address,
            'role': role,
            'iat': time.time(),
            'exp': time.time() + (self.expiration_hours * 3600),
            'jti': secrets.token_hex(16)
        }
        return jwt.encode(payload, self.secret_key, algorithm=ALGORITHM)
    
    def verify_token(self, token: str) -> Tuple[bool, Optional[Dict]]:
        if token in self.blacklist:
            return False, None
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[ALGORITHM])
            return True, payload
        except:
            return False, None
    
    def revoke_token(self, token: str) -> None:
        self.blacklist.add(token)

jwt_auth = JWTAuth()
