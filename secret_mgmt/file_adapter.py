# secrets/file_adapter.py — Dev-only wallet.json secret backend (ADR 0015)
"""Read private_key from a wallet JSON file. Prod refuses this adapter."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from secret_mgmt.ports import (
    SECRET_NODE_BFT_SIGNING_KEY,
    SECRET_NODE_WALLET_PRIVATE_KEY,
    SecretNotFoundError,
)

logger = logging.getLogger("secret_mgmt.file")


class FileSecretAdapter:
    """SECRET_BACKEND=file — load node/BFT key from wallet.json (dev only)."""

    def __init__(
        self,
        wallet_path: str,
        *,
        deployment_mode: str = "dev",
        allow_prod: bool = False,
    ) -> None:
        mode = (deployment_mode or "dev").strip().lower()
        if mode in ("prod", "production") and not allow_prod:
            raise RuntimeError("FileSecretAdapter refused in production (ADR 0015)")
        self._path = Path(wallet_path)
        self._deployment_mode = mode

    def _load_private_key(self) -> str:
        if not self._path.is_file():
            raise SecretNotFoundError(SECRET_NODE_WALLET_PRIVATE_KEY)
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("wallet_file_unreadable")
            raise SecretNotFoundError(SECRET_NODE_WALLET_PRIVATE_KEY) from exc
        pk = str((raw or {}).get("private_key", "") or "").strip()
        if not pk:
            raise SecretNotFoundError(SECRET_NODE_WALLET_PRIVATE_KEY)
        return pk

    def get_secret(self, name: str) -> str:
        if name in (SECRET_NODE_WALLET_PRIVATE_KEY, SECRET_NODE_BFT_SIGNING_KEY):
            return self._load_private_key()
        raise SecretNotFoundError(name)

    def get_bytes(self, name: str) -> bytes:
        return self.get_secret(name).encode("utf-8")

    def has_secret(self, name: str) -> bool:
        try:
            self.get_secret(name)
            return True
        except SecretNotFoundError:
            return False

    def __repr__(self) -> str:
        return f"FileSecretAdapter(path={self._path.name!r}, redacted)"

    def __str__(self) -> str:
        return self.__repr__()
