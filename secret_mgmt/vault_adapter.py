# secrets/vault_adapter.py — HashiCorp Vault KV v2 HTTP backend (ADR 0015)
"""Fetch secrets from Vault KV; never log token or secret values."""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Mapping, Optional

from secret_mgmt.ports import (
    SECRET_API_JWT,
    SECRET_API_RPC_KEYS,
    SECRET_BRIDGE_ORACLE,
    SECRET_EXTERNAL_SIGNER_API_KEY,
    SECRET_EXTERNAL_SIGNER_URL,
    SECRET_NODE_BFT_SIGNING_KEY,
    SECRET_NODE_WALLET_PRIVATE_KEY,
    SecretNotFoundError,
)

logger = logging.getLogger("secret_mgmt.vault")

# Logical → Vault data field names inside KV payload.
_VAULT_FIELD_MAP: Mapping[str, tuple[str, ...]] = {
    SECRET_NODE_WALLET_PRIVATE_KEY: ("wallet_private_key", "WALLET_PRIVATE_KEY"),
    SECRET_NODE_BFT_SIGNING_KEY: (
        "bft_signing_key",
        "BFT_SIGNING_KEY",
        "wallet_private_key",
        "WALLET_PRIVATE_KEY",
    ),
    SECRET_API_JWT: ("jwt_secret", "JWT_SECRET"),
    SECRET_API_RPC_KEYS: ("rpc_api_keys", "RPC_API_KEYS"),
    SECRET_BRIDGE_ORACLE: ("bridge_oracle_secret", "BRIDGE_ORACLE_SECRET"),
    SECRET_EXTERNAL_SIGNER_URL: (
        "external_validator_signer_url",
        "EXTERNAL_VALIDATOR_SIGNER_URL",
    ),
    SECRET_EXTERNAL_SIGNER_API_KEY: (
        "external_validator_signer_api_key",
        "EXTERNAL_VALIDATOR_SIGNER_API_KEY",
    ),
}


class VaultKvSecretAdapter:
    """SECRET_BACKEND=vault — HashiCorp Vault KV v2 over HTTP.

    Config (env):
      VAULT_ADDR, VAULT_TOKEN, VAULT_KV_PATH (e.g. secret/data/abs/node),
      VAULT_CACHE_TTL_SEC (default 60).
    """

    def __init__(
        self,
        *,
        addr: str = "",
        token: str = "",
        kv_path: str = "",
        cache_ttl_sec: float = 60.0,
        timeout: float = 5.0,
        http_get=None,
    ) -> None:
        self._addr = (addr or os.environ.get("VAULT_ADDR", "") or "").rstrip("/")
        self._token = (token or os.environ.get("VAULT_TOKEN", "") or "").strip()
        self._kv_path = (
            kv_path or os.environ.get("VAULT_KV_PATH", "") or "secret/data/abs/node"
        ).strip().lstrip("/")
        self._cache_ttl = max(1.0, float(cache_ttl_sec or os.environ.get("VAULT_CACHE_TTL_SEC", 60) or 60))
        self._timeout = max(1.0, float(timeout))
        self._http_get = http_get  # injectable for tests
        self._cache: Dict[str, Any] = {}
        self._cache_at: float = 0.0

    def _fetch_data(self) -> Mapping[str, Any]:
        now = time.time()
        if self._cache and (now - self._cache_at) < self._cache_ttl:
            return self._cache
        if not self._addr or not self._token:
            raise SecretNotFoundError("vault_config")
        url = f"{self._addr}/v1/{self._kv_path}"
        if self._http_get is not None:
            payload = self._http_get(url, self._token)
        else:
            req = urllib.request.Request(
                url,
                headers={"X-Vault-Token": self._token},
                method="GET",
            )
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                logger.warning("vault_kv_http_error status=%s", exc.code)
                raise SecretNotFoundError("vault_http") from exc
            except Exception as exc:
                logger.warning("vault_kv_unreachable")
                raise SecretNotFoundError("vault_unreachable") from exc
        data = {}
        if isinstance(payload, dict):
            # KV v2: data.data ; KV v1: data
            inner = payload.get("data")
            if isinstance(inner, dict) and isinstance(inner.get("data"), dict):
                data = dict(inner["data"])
            elif isinstance(inner, dict):
                data = dict(inner)
        self._cache = data
        self._cache_at = now
        logger.info("vault_kv_refreshed path=%s keys=%d", self._kv_path, len(data))
        return data

    def _lookup(self, name: str) -> str:
        data = self._fetch_data()
        fields = _VAULT_FIELD_MAP.get(name, (name,))
        for field in fields:
            val = str(data.get(field, "") or "").strip()
            if val:
                return val
        raise SecretNotFoundError(name)

    def get_secret(self, name: str) -> str:
        return self._lookup(name)

    def get_bytes(self, name: str) -> bytes:
        return self._lookup(name).encode("utf-8")

    def has_secret(self, name: str) -> bool:
        try:
            self._lookup(name)
            return True
        except SecretNotFoundError:
            return False

    def __repr__(self) -> str:
        return f"VaultKvSecretAdapter(addr={'set' if self._addr else 'unset'}, redacted)"

    def __str__(self) -> str:
        return self.__repr__()
