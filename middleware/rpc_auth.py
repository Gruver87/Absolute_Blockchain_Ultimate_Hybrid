#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RPC API key authentication (промышленный профиль)."""

import hmac
import os
import secrets
from typing import List, Optional, Set, Tuple


class RPCApiKeyAuth:
    """Проверка X-API-Key / Authorization: Bearer для JSON-RPC."""

    def __init__(self, keys: Optional[List[str]] = None, required: bool = False):
        self.required = required
        # Preserve order for constant-time scan; dedupe while keeping first occurrence.
        seen: Set[str] = set()
        ordered: List[str] = []
        for k in keys or []:
            s = str(k).strip()
            if not s or s in seen:
                continue
            seen.add(s)
            ordered.append(s)
        self._keys: Tuple[str, ...] = tuple(ordered)

    @classmethod
    def from_config(cls, config) -> "RPCApiKeyAuth":
        keys = list(getattr(config, "rpc_api_keys", []) or [])
        env_keys = os.getenv("RPC_API_KEYS", "")
        if env_keys.strip():
            keys.extend(x.strip() for x in env_keys.split(",") if x.strip())
        required = bool(getattr(config, "rpc_api_key_required", False))
        return cls(keys=keys, required=required)

    @property
    def enabled(self) -> bool:
        return self.required and bool(self._keys)

    def extract_key(self, headers) -> str:
        if not headers:
            return ""
        api_key = headers.get("X-API-Key", headers.get("x-api-key", "")).strip()
        if api_key:
            return api_key
        auth = headers.get("Authorization", headers.get("authorization", ""))
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return ""

    def _key_matches(self, provided: str) -> bool:
        """Constant-time compare against all configured keys."""
        if not provided or not self._keys:
            return False
        matched = False
        for candidate in self._keys:
            # compare_digest requires equal length; pad via hmac of both sides
            # so length differences do not short-circuit the whole scan.
            a = hmac.new(b"abs-rpc-key", provided.encode("utf-8"), "sha256").digest()
            b = hmac.new(b"abs-rpc-key", candidate.encode("utf-8"), "sha256").digest()
            if hmac.compare_digest(a, b):
                matched = True
        return matched

    def verify(self, headers) -> tuple:
        """
        Returns (allowed: bool, error_message: str).
        Если required=False — всегда allowed.
        """
        if not self.required:
            return True, ""
        if not self._keys:
            return False, "RPC API keys not configured (set RPC_API_KEYS)"
        key = self.extract_key(headers)
        if not key:
            return False, "Missing X-API-Key or Authorization: Bearer"
        if not self._key_matches(key):
            return False, "Invalid RPC API key"
        return True, ""

    @staticmethod
    def generate_key() -> str:
        return secrets.token_urlsafe(32)
