# secret_mgmt/__init__.py — ADR 0015 secret management package
"""Logical secret resolution (env/K8s, Vault KV, file). Named ``secret_mgmt`` to avoid shadowing stdlib ``secrets``."""

from secret_mgmt.factory import build_secret_manager
from secret_mgmt.ports import (
    SECRET_API_JWT,
    SECRET_API_RPC_KEYS,
    SECRET_BRIDGE_ORACLE,
    SECRET_NODE_BFT_SIGNING_KEY,
    SECRET_NODE_WALLET_PRIVATE_KEY,
    NullSecretManager,
    SecretManagerPort,
    SecretNotFoundError,
)

__all__ = [
    "SECRET_API_JWT",
    "SECRET_API_RPC_KEYS",
    "SECRET_BRIDGE_ORACLE",
    "SECRET_NODE_BFT_SIGNING_KEY",
    "SECRET_NODE_WALLET_PRIVATE_KEY",
    "NullSecretManager",
    "SecretManagerPort",
    "SecretNotFoundError",
    "build_secret_manager",
]
