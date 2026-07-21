# middleware/jwt_auth.py
import jwt
import secrets
import time
import os
from typing import Dict, Optional, Tuple

ALGORITHM = "HS256"


def _resolve_jwt_secret() -> str:
    """Resolve JWT secret from live env (after dotenv), not frozen at import."""
    secret = os.getenv("JWT_SECRET", "").strip()
    if secret:
        return secret
    if os.getenv("DEPLOYMENT_MODE", "dev").lower() == "prod":
        return ""
    return ""


class JWTAuth:
    """JWT авторизация — secret always re-read from JWT_SECRET when set."""

    def __init__(self):
        self._dev_fallback = ""
        self.expiration_hours = 24
        self.blacklist = set()

    @property
    def secret_key(self) -> str:
        env = _resolve_jwt_secret()
        if env:
            return env
        if os.getenv("DEPLOYMENT_MODE", "dev").lower() == "prod":
            return ""
        if not self._dev_fallback:
            self._dev_fallback = secrets.token_hex(32)
        return self._dev_fallback

    @secret_key.setter
    def secret_key(self, value: str) -> None:
        # Allow ops scripts (mint_admin_jwt) to pin a secret for the process.
        value = str(value or "").strip()
        if value:
            os.environ["JWT_SECRET"] = value
            self._dev_fallback = ""
        else:
            self._dev_fallback = ""

    def generate_token(self, address: str, role: str = "user") -> str:
        key = self.secret_key
        if not key:
            raise RuntimeError("JWT_SECRET not configured")
        role_n = str(role or "user").strip().lower() or "user"
        if role_n not in ("user", "admin"):
            raise ValueError(f"invalid JWT role: {role_n}")
        payload = {
            "address": address,
            "role": role_n,
            "iat": time.time(),
            "exp": time.time() + (self.expiration_hours * 3600),
            "jti": secrets.token_hex(16),
        }
        return jwt.encode(payload, key, algorithm=ALGORITHM)

    def verify_token(self, token: str) -> Tuple[bool, Optional[Dict]]:
        key = self.secret_key
        if not key:
            return False, None
        if token in self.blacklist:
            return False, None
        try:
            payload = jwt.decode(token, key, algorithms=[ALGORITHM])
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


# Backward-compat module alias used by older scripts
SECRET_KEY = ""  # do not freeze; use jwt_auth.secret_key
jwt_auth = JWTAuth()
