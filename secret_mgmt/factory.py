# secrets/factory.py — build SecretManagerPort from config / env (ADR 0015)
"""Factory: SECRET_BACKEND=env|vault|file → SecretManagerPort."""

from __future__ import annotations

import os
from typing import Any, Optional

from secret_mgmt.env_adapter import EnvK8sSecretAdapter
from secret_mgmt.ports import NullSecretManager, SecretManagerPort


def build_secret_manager(
    config: Any = None,
    *,
    wallet_path: str = "",
    backend: Optional[str] = None,
) -> SecretManagerPort:
    """Construct the process-wide secret manager.

    Backend resolution order:
      1. explicit ``backend`` arg
      2. ``config.secret_backend`` if present
      3. ``SECRET_BACKEND`` env (default ``env``)
    """
    mode = (
        (backend or "")
        or str(getattr(config, "secret_backend", "") or "")
        or os.environ.get("SECRET_BACKEND", "env")
        or "env"
    ).strip().lower()
    deployment = str(
        getattr(config, "deployment_mode", None)
        or os.environ.get("DEPLOYMENT_MODE", "dev")
        or "dev"
    ).strip().lower()
    prod = deployment in ("prod", "production")

    if mode in ("null", "none", "off"):
        if prod:
            raise RuntimeError(
                "SECRET_BACKEND=null/off refused in production (ADR 0015)"
            )
        return NullSecretManager()

    if mode == "vault":
        addr = (
            os.environ.get("VAULT_ADDR", "")
            or str(getattr(config, "vault_addr", "") or "")
        ).strip()
        if prod and addr and not addr.lower().startswith("https://"):
            raise RuntimeError(
                "prod SECRET_BACKEND=vault requires VAULT_ADDR https://"
            )
        from secret_mgmt.vault_adapter import VaultKvSecretAdapter

        return VaultKvSecretAdapter()

    if mode == "file":
        if prod:
            raise RuntimeError(
                "SECRET_BACKEND=file refused in production (ADR 0015)"
            )
        from secret_mgmt.file_adapter import FileSecretAdapter

        path = (
            wallet_path
            or str(getattr(config, "wallet_path", "") or "")
            or os.environ.get("WALLET_PATH", "")
            or ""
        )
        if not path:
            raise RuntimeError("SECRET_BACKEND=file requires wallet_path")
        return FileSecretAdapter(path, deployment_mode=deployment)

    # Default: env / K8s Secret→env
    return EnvK8sSecretAdapter()
