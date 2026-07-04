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


class AwsCloudHsmKeyProvider(ExternalSignerKeyProvider):
    """AWS CloudHSM via PKCS#11 HTTP signing proxy (sidecar or custom signer)."""

    def __init__(self, url: str = "", api_key: str = "", timeout: float = 10.0) -> None:
        resolved = (url or os.environ.get("AWS_CLOUDHSM_SIGNER_URL", "") or "").strip()
        if not resolved:
            resolved = os.environ.get("EXTERNAL_VALIDATOR_SIGNER_URL", "").strip()
        token = (api_key or os.environ.get("AWS_CLOUDHSM_SIGNER_API_KEY", "") or "").strip()
        if not token:
            token = os.environ.get("EXTERNAL_VALIDATOR_SIGNER_API_KEY", "").strip()
        super().__init__(resolved, token, timeout)

    def sign_message(self, message: bytes) -> bytes:
        if not self.url:
            raise RuntimeError("aws_cloudhsm_signer_url_missing")
        return super().sign_message(message)


class AwsKmsKeyProvider:
    """Sign validator payloads via AWS KMS (requires boto3)."""

    def __init__(self, key_id: str, region: str = "") -> None:
        self.key_id = (key_id or "").strip()
        self.region = (region or os.environ.get("AWS_REGION", "us-east-1")).strip()
        self._pubkey = ""

    def sign_message(self, message: bytes) -> bytes:
        if not self.key_id:
            raise RuntimeError("aws_kms_key_id_missing")
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("boto3_required_for_aws_kms") from exc
        client = boto3.client("kms", region_name=self.region)
        digest = __import__("hashlib").sha256(message).digest()
        resp = client.sign(
            KeyId=self.key_id,
            Message=digest,
            MessageType="DIGEST",
            SigningAlgorithm="ECDSA_SHA_256",
        )
        sig = resp.get("Signature")
        if not sig:
            raise RuntimeError("aws_kms_empty_signature")
        return bytes(sig)

    def public_key_hex(self) -> str:
        return self._pubkey


def _gcp_kms_key_version_from_env() -> str:
    direct = (os.environ.get("GCP_KMS_KEY_VERSION", "") or "").strip()
    if direct:
        return direct
    project = (os.environ.get("GCP_PROJECT_ID", "") or "").strip()
    location = (os.environ.get("GCP_KMS_LOCATION", "global") or "global").strip()
    ring = (os.environ.get("GCP_KMS_KEY_RING", "") or "").strip()
    key = (os.environ.get("GCP_KMS_KEY_NAME", "") or "").strip()
    version = (os.environ.get("GCP_KMS_KEY_VERSION_ID", "1") or "1").strip()
    if project and ring and key:
        return (
            f"projects/{project}/locations/{location}/keyRings/{ring}"
            f"/cryptoKeys/{key}/cryptoKeyVersions/{version}"
        )
    return ""


class GcpKmsKeyProvider:
    """Sign validator payloads via Google Cloud KMS (requires google-cloud-kms)."""

    def __init__(self, key_version: str) -> None:
        self.key_version = (key_version or "").strip()
        self._pubkey = ""

    def _kms_client(self):
        from google.cloud import kms
        return kms.KeyManagementServiceClient()

    def sign_message(self, message: bytes) -> bytes:
        if not self.key_version:
            raise RuntimeError("gcp_kms_key_version_missing")
        try:
            client = self._kms_client()
        except ImportError as exc:
            raise RuntimeError("google_cloud_kms_required") from exc
        digest = __import__("hashlib").sha256(message).digest()
        response = client.asymmetric_sign(
            request={
                "name": self.key_version,
                "digest": {"sha256": digest},
            }
        )
        sig = response.signature
        if not sig:
            raise RuntimeError("gcp_kms_empty_signature")
        return bytes(sig)

    def public_key_hex(self) -> str:
        return self._pubkey


class GcpCloudHsmKeyProvider(GcpKmsKeyProvider):
    """GCP KMS key with HSM protection level (Cloud HSM cluster backed)."""

    def __init__(self, key_version: str) -> None:
        super().__init__(key_version)
        self._hsm_verified = False

    def _ensure_hsm_protection(self) -> None:
        if self._hsm_verified:
            return
        try:
            client = self._kms_client()
        except ImportError as exc:
            raise RuntimeError("google_cloud_kms_required") from exc
        version = client.get_crypto_key_version(name=self.key_version)
        level = getattr(version, "protection_level", None)
        level_name = str(getattr(level, "name", level) or "").upper()
        if level_name != "HSM" and level != 2:
            raise RuntimeError(
                f"gcp_key_not_hsm_backed: protection_level={level_name or level}"
            )
        self._hsm_verified = True

    def sign_message(self, message: bytes) -> bytes:
        self._ensure_hsm_protection()
        return super().sign_message(message)


def build_validator_key_provider(wallet=None) -> ValidatorKeyProvider:
    mode = (os.environ.get("VALIDATOR_KEY_PROVIDER", "local") or "local").strip().lower()
    if mode == "external":
        url = os.environ.get("EXTERNAL_VALIDATOR_SIGNER_URL", "").strip()
        api_key = os.environ.get("EXTERNAL_VALIDATOR_SIGNER_API_KEY", "").strip()
        return ExternalSignerKeyProvider(url, api_key)
    if mode in ("aws_kms", "kms"):
        key_id = os.environ.get("AWS_KMS_KEY_ID", "").strip()
        region = os.environ.get("AWS_REGION", "").strip()
        return AwsKmsKeyProvider(key_id, region)
    if mode in ("aws_cloudhsm", "cloudhsm"):
        return AwsCloudHsmKeyProvider()
    if mode in ("gcp_kms", "google_kms"):
        key_version = _gcp_kms_key_version_from_env()
        return GcpKmsKeyProvider(key_version)
    if mode in ("gcp_cloudhsm", "gcp_hsm", "cloudhsm"):
        key_version = _gcp_kms_key_version_from_env()
        return GcpCloudHsmKeyProvider(key_version)
    return LocalWalletKeyProvider(wallet)
