# secrets/ports.py — ADR 0015 SecretManagerPort
"""Logical secret resolution — env/K8s, Vault KV, or file backends."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

# Stable logical ids (adapters map these to env / Vault keys).
SECRET_NODE_WALLET_PRIVATE_KEY = "node.wallet_private_key"
SECRET_NODE_BFT_SIGNING_KEY = "node.bft_signing_key"
SECRET_API_JWT = "api.jwt_secret"
SECRET_API_RPC_KEYS = "api.rpc_api_keys"
SECRET_BRIDGE_ORACLE = "bridge.oracle_secret"
SECRET_EXTERNAL_SIGNER_URL = "validator.external_signer_url"
SECRET_EXTERNAL_SIGNER_API_KEY = "validator.external_signer_api_key"


@runtime_checkable
class SecretManagerPort(Protocol):
    def get_secret(self, name: str) -> str:
        ...

    def get_bytes(self, name: str) -> bytes:
        ...

    def has_secret(self, name: str) -> bool:
        ...


class SecretNotFoundError(LookupError):
    """Raised when a required secret is missing (fail-closed)."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"secret_not_found:{name}")


class NullSecretManager:
    """Empty secret store for tests that do not need key material."""

    def get_secret(self, name: str) -> str:
        raise SecretNotFoundError(name)

    def get_bytes(self, name: str) -> bytes:
        raise SecretNotFoundError(name)

    def has_secret(self, name: str) -> bool:
        return False

    def __repr__(self) -> str:
        return "NullSecretManager(redacted)"

    def __str__(self) -> str:
        return self.__repr__()
