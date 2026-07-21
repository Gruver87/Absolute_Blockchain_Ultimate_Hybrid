# middleware/jwt_auth.py
import jwt
import secrets
import time
import os
from typing import Dict, Optional, Tuple

# Секретный ключ из переменных окружения (prod: обязателен, без random fallback)
def _resolve_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "").strip()
    if secret:
        return secret
    if os.getenv("DEPLOYMENT_MODE", "dev").lower() == "prod":
        return ""
    return secrets.token_hex(32)


SECRET_KEY = _resolve_jwt_secret()
ALGORITHM = "HS256"

class JWTAuth:
    """JWT авторизация"""
    
    def __init__(self):
        self.secret_key = SECRET_KEY
        self.expiration_hours = 24
        self.blacklist = set()
    
    def generate_token(self, address: str, role: str = "user") -> str:
        if not self.secret_key:
            raise RuntimeError("JWT_SECRET not configured")
        role_n = str(role or "user").strip().lower() or "user"
        if role_n not in ("user", "admin"):
            raise ValueError(f"invalid JWT role: {role_n}")
        payload = {
            'address': address,
            'role': role_n,
            'iat': time.time(),
            'exp': time.time() + (self.expiration_hours * 3600),
            'jti': secrets.token_hex(16)
        }
        return jwt.encode(payload, self.secret_key, algorithm=ALGORITHM)
    
    def verify_token(self, token: str) -> Tuple[bool, Optional[Dict]]:
        if not self.secret_key:
            return False, None
        if token in self.blacklist:
            return False, None
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[ALGORITHM])
            return True, payload
        except Exception:
            return False, None

    def require_role(self, token: str, role: str = "admin") -> Tuple[bool, Optional[Dict], str]:
        """Verify token and enforce role. Returns (ok, payload, error)."""
        ok, payload = self.verify_token(token)
        if not ok or not payload:
            return False, None, "Invalid or expired JWT"
        have = str(payload.get("role") or "").strip().lower()
        need = str(role or "admin").strip().lower()
        if have != need:
            return False, payload, f"JWT role '{have or 'none'}' insufficient (need {need})"
        return True, payload, ""
    
    def revoke_token(self, token: str) -> None:
        self.blacklist.add(token)

jwt_auth = JWTAuth()
