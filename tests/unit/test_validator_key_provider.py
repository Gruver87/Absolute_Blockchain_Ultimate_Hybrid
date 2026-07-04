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
