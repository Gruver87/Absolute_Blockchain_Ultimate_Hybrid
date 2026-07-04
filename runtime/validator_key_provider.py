#!/usr/bin/env python3
"""Validator signing key providers — local wallet vs external HSM/KMS signer."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Optional, Protocol


class ValidatorKeyProvider(Protocol):
    def sign_message(self, message: bytes) -> bytes:
        ...

    def public_key_hex(self) -> str:
        ...


class LocalWalletKeyProvider:
    """Sign with in-process wallet (dev / file-backed)."""

    def __init__(self, wallet) -> None:
        self._wallet = wallet

    def sign_message(self, message: bytes) -> bytes:
        if not self._wallet or not hasattr(self._wallet, "sign_message"):
            raise RuntimeError("wallet_signing_unavailable")
        sig = self._wallet.sign_message(message)
        if isinstance(sig, str):
            return bytes.fromhex(sig.replace("0x", ""))
        return bytes(sig)

    def public_key_hex(self) -> str:
        if not self._wallet:
            return ""
        return str(getattr(self._wallet, "public_key", "") or getattr(self._wallet, "pubkey", "") or "")


class ExternalSignerKeyProvider:
    """Delegate signing to an external HSM/KMS HTTP endpoint."""

    def __init__(self, url: str, api_key: str = "", timeout: float = 5.0) -> None:
        self.url = (url or "").strip()
        self.api_key = (api_key or "").strip()
        self.timeout = float(timeout)
        self._pubkey = ""

    def sign_message(self, message: bytes) -> bytes:
        if not self.url:
            raise RuntimeError("external_signer_url_missing")
        payload = json.dumps({
            "message": "0x" + message.hex(),
        }).encode()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(self.url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode())
        except urllib.error.URLError as exc:
            raise RuntimeError(f"external_signer_unreachable: {exc}") from exc
        sig = body.get("signature", body.get("sig", ""))
        if not sig:
            raise RuntimeError("external_signer_empty_signature")
        self._pubkey = str(body.get("public_key", body.get("pubkey", self._pubkey)) or "")
        return bytes.fromhex(str(sig).replace("0x", ""))

    def public_key_hex(self) -> str:
        return self._pubkey


def build_validator_key_provider(wallet=None) -> ValidatorKeyProvider:
    mode = (os.environ.get("VALIDATOR_KEY_PROVIDER", "local") or "local").strip().lower()
    if mode == "external":
        url = os.environ.get("EXTERNAL_VALIDATOR_SIGNER_URL", "").strip()
        api_key = os.environ.get("EXTERNAL_VALIDATOR_SIGNER_API_KEY", "").strip()
        return ExternalSignerKeyProvider(url, api_key)
    return LocalWalletKeyProvider(wallet)
