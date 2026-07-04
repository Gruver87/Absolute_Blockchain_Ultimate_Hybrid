#!/usr/bin/env python3
"""Validator key provider local vs external signer."""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.validator_key_provider import (
    ExternalSignerKeyProvider,
    LocalWalletKeyProvider,
    build_validator_key_provider,
)


def test_local_wallet_provider_signs():
    wallet = MagicMock()
    wallet.sign_message.return_value = "0x" + "ab" * 32
    wallet.public_key = "0xpub"
    provider = LocalWalletKeyProvider(wallet)
    sig = provider.sign_message(b"hello")
    assert len(sig) == 32
    assert provider.public_key_hex() == "0xpub"


def test_external_signer_provider():
    provider = ExternalSignerKeyProvider("http://signer.local/sign")

    class FakeResp:
        def read(self):
            return json.dumps({
                "signature": "0x" + "cd" * 32,
                "public_key": "0xext",
            }).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with patch("urllib.request.urlopen", return_value=FakeResp()):
        sig = provider.sign_message(b"msg")
    assert len(sig) == 32
    assert provider.public_key_hex() == "0xext"


def test_build_provider_modes(monkeypatch):
    wallet = MagicMock()
    monkeypatch.delenv("VALIDATOR_KEY_PROVIDER", raising=False)
    assert isinstance(build_validator_key_provider(wallet), LocalWalletKeyProvider)
    monkeypatch.setenv("VALIDATOR_KEY_PROVIDER", "external")
    monkeypatch.setenv("EXTERNAL_VALIDATOR_SIGNER_URL", "http://localhost/sign")
    assert isinstance(build_validator_key_provider(wallet), ExternalSignerKeyProvider)
    monkeypatch.setenv("VALIDATOR_KEY_PROVIDER", "aws_kms")
    monkeypatch.setenv("AWS_KMS_KEY_ID", "arn:aws:kms:us-east-1:1:key/1")
    from runtime.validator_key_provider import AwsKmsKeyProvider
    assert isinstance(build_validator_key_provider(wallet), AwsKmsKeyProvider)
    monkeypatch.setenv("VALIDATOR_KEY_PROVIDER", "gcp_kms")
    monkeypatch.setenv(
        "GCP_KMS_KEY_VERSION",
        "projects/p/locations/global/keyRings/r/cryptoKeys/k/cryptoKeyVersions/1",
    )
    from runtime.validator_key_provider import GcpKmsKeyProvider
    assert isinstance(build_validator_key_provider(wallet), GcpKmsKeyProvider)


def test_gcp_kms_provider_signs(monkeypatch):
    from runtime.validator_key_provider import GcpKmsKeyProvider

    provider = GcpKmsKeyProvider(
        "projects/p/locations/global/keyRings/r/cryptoKeys/k/cryptoKeyVersions/1"
    )
    fake_client = MagicMock()
    fake_client.asymmetric_sign.return_value = MagicMock(signature=b"\x01" * 64)
    fake_kms = MagicMock()
    fake_kms.KeyManagementServiceClient.return_value = fake_client

    with patch.dict("sys.modules", {"google": MagicMock(), "google.cloud": MagicMock(kms=fake_kms)}):
        sig = provider.sign_message(b"payload")
    assert sig == b"\x01" * 64
    fake_client.asymmetric_sign.assert_called_once()


def test_gcp_kms_key_version_from_env_parts(monkeypatch):
    monkeypatch.setenv("VALIDATOR_KEY_PROVIDER", "gcp_kms")
    monkeypatch.delenv("GCP_KMS_KEY_VERSION", raising=False)
    monkeypatch.setenv("GCP_PROJECT_ID", "my-proj")
    monkeypatch.setenv("GCP_KMS_LOCATION", "europe-west1")
    monkeypatch.setenv("GCP_KMS_KEY_RING", "validators")
    monkeypatch.setenv("GCP_KMS_KEY_NAME", "node-1")
    monkeypatch.setenv("GCP_KMS_KEY_VERSION_ID", "3")
    from runtime.validator_key_provider import GcpKmsKeyProvider, build_validator_key_provider

    provider = build_validator_key_provider()
    assert isinstance(provider, GcpKmsKeyProvider)
    assert provider.key_version.endswith("/cryptoKeyVersions/3")
    assert "projects/my-proj/locations/europe-west1" in provider.key_version
