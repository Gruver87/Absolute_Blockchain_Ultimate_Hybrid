# secrets/env_adapter.py — Env / K8s Secret→env backend (ADR 0015)
"""Resolve logical secrets from process environment (K8s Opaque Secret mounts)."""

from __future__ import annotations

import os
from typing import Mapping, Optional

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

# Logical name → preferred env var (K8s stringData keys match these).
_ENV_MAP: Mapping[str, tuple[str, ...]] = {
    SECRET_NODE_WALLET_PRIVATE_KEY: ("WALLET_PRIVATE_KEY",),
    SECRET_NODE_BFT_SIGNING_KEY: ("BFT_SIGNING_KEY", "WALLET_PRIVATE_KEY"),
    SECRET_API_JWT: ("JWT_SECRET",),
    SECRET_API_RPC_KEYS: ("RPC_API_KEYS",),
    SECRET_BRIDGE_ORACLE: ("BRIDGE_ORACLE_SECRET",),
    SECRET_EXTERNAL_SIGNER_URL: ("EXTERNAL_VALIDATOR_SIGNER_URL",),
    SECRET_EXTERNAL_SIGNER_API_KEY: ("EXTERNAL_VALIDATOR_SIGNER_API_KEY",),
}


class EnvK8sSecretAdapter:
    """Default SECRET_BACKEND=env — K8s Secrets injected as environment variables."""

    def __init__(self, environ: Optional[Mapping[str, str]] = None) -> None:
        self._env = environ if environ is not None else os.environ

    def _lookup(self, name: str) -> str:
        keys = _ENV_MAP.get(name)
        if keys is None:
            # Prod fail-closed: unknown logical names must not raw-read env.
            allow_raw = str(
                self._env.get("ABS_SECRET_ALLOW_RAW", "") or ""
            ).strip().lower() in ("1", "true", "yes", "on")
            deployment = str(
                self._env.get("DEPLOYMENT_MODE", "") or self._env.get("ABS_DEPLOYMENT_MODE", "") or ""
            ).strip().lower()
            if deployment in ("prod", "production", "mainnet") and not allow_raw:
                raise SecretNotFoundError(name)
            raw = str(self._env.get(name, "") or "").strip()
            if raw:
                return raw
            raise SecretNotFoundError(name)
        for key in keys:
            val = str(self._env.get(key, "") or "").strip()
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
        return "EnvK8sSecretAdapter(redacted)"

    def __str__(self) -> str:
        return self.__repr__()
