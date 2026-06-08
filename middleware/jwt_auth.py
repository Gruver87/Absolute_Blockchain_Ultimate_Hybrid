#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JWT авторизация для API"""

import jwt
import hashlib
import secrets
import time
from typing import Dict, Optional, Tuple
from functools import wraps
from datetime import datetime, timedelta

# Секретный ключ (в production брать из переменных окружения)
SECRET_KEY = "absolute_blockchain_jwt_secret_2024"
ALGORITHM = "HS256"

class JWTAuth:
    """Управление JWT токенами"""
    
    def __init__(self, secret_key: str = SECRET_KEY, expiration_hours: int = 24):
        self.secret_key = secret_key
        self.expiration_hours = expiration_hours
        self.blacklist = set()  # Черный список токенов
    
    def generate_token(self, address: str, role: str = "user") -> str:
        """Генерация JWT токена"""
        payload = {
            'address': address,
            'role': role,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(hours=self.expiration_hours),
            'jti': secrets.token_hex(16)
        }
        return jwt.encode(payload, self.secret_key, algorithm=ALGORITHM)
    
    def verify_token(self, token: str) -> Tuple[bool, Optional[Dict]]:
        """
        Проверка токена
        Возвращает: (валиден, payload)
        """
        if token in self.blacklist:
            return False, None
        
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[ALGORITHM])
            return True, payload
        except jwt.ExpiredSignatureError:
            return False, None
        except jwt.InvalidTokenError:
            return False, None
    
    def revoke_token(self, token: str) -> None:
        """Отозвать токен (при выходе)"""
        self.blacklist.add(token)
    
    def refresh_token(self, token: str) -> Optional[str]:
        """Обновление токена"""
        valid, payload = self.verify_token(token)
        if not valid or payload is None:
            return None
        
        # Отзываем старый токен
        self.revoke_token(token)
        
        # Генерируем новый
        return self.generate_token(payload['address'], payload.get('role', 'user'))

# Глобальный экземпляр
jwt_auth = JWTAuth()

def require_auth(func):
    """Декоратор для защиты эндпоинтов"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        # Получаем токен из заголовка Authorization
        auth_header = self.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            self._send_json({'error': 'Missing or invalid token'}, 401)
            return None
        
        token = auth_header[7:]  # Убираем 'Bearer '
        valid, payload = jwt_auth.verify_token(token)
        
        if not valid:
            self._send_json({'error': 'Invalid or expired token'}, 401)
            return None
        
        # Добавляем payload в запрос
        self.auth_payload = payload
        return func(self, *args, **kwargs)
    return wrapper
