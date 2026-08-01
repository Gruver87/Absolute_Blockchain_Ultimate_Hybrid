# tests/unit/test_secrets_isolation.py — ADR 0015 SecretManagerPort leak fence
"""Prove private key material is never logged and never written to DB meta."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from secret_mgmt.env_adapter import EnvK8sSecretAdapter
from secret_mgmt.factory import build_secret_manager
from secret_mgmt.file_adapter import FileSecretAdapter
from secret_mgmt.ports import (
    SECRET_NODE_BFT_SIGNING_KEY,
    SECRET_NODE_WALLET_PRIVATE_KEY,
    SecretNotFoundError,
)
from secret_mgmt.vault_adapter import VaultKvSecretAdapter


SECRET_HEX = "a" * 64


class _CapturingHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(self.format(record))


class _FakeDB:
    def __init__(self) -> None:
        self.meta: dict = {}

    def set_meta(self, key, value) -> None:
        self.meta[key] = value

    def get_meta(self, key, default=None):
        return self.meta.get(key, default)


def test_env_adapter_resolves_wallet_and_bft_fallback():
    env = {"WALLET_PRIVATE_KEY": SECRET_HEX}
    sm = EnvK8sSecretAdapter(environ=env)
    assert sm.get_secret(SECRET_NODE_WALLET_PRIVATE_KEY) == SECRET_HEX
    assert sm.get_secret(SECRET_NODE_BFT_SIGNING_KEY) == SECRET_HEX
    assert sm.has_secret(SECRET_NODE_WALLET_PRIVATE_KEY) is True
    assert "a" * 8 not in repr(sm)
    assert SECRET_HEX not in str(sm)
    assert "redacted" in repr(sm)


def test_env_adapter_missing_raises():
    sm = EnvK8sSecretAdapter(environ={})
    with pytest.raises(SecretNotFoundError):
        sm.get_secret(SECRET_NODE_WALLET_PRIVATE_KEY)


def test_vault_adapter_kv_v2_and_no_token_in_logs():
    payload = {
        "data": {
            "data": {
                "wallet_private_key": SECRET_HEX,
                "bft_signing_key": "b" * 64,
            }
        }
    }

    def _fake_get(url, token):
        assert token == "s.vault-token-secret"
        assert "secret/data/abs/node" in url
        return payload

    sm = VaultKvSecretAdapter(
        addr="http://vault.test:8200",
        token="s.vault-token-secret",
        kv_path="secret/data/abs/node",
        http_get=_fake_get,
    )
    cap = _CapturingHandler()
    log = logging.getLogger("secret_mgmt.vault")
    log.addHandler(cap)
    log.setLevel(logging.INFO)
    try:
        assert sm.get_secret(SECRET_NODE_WALLET_PRIVATE_KEY) == SECRET_HEX
        assert sm.get_secret(SECRET_NODE_BFT_SIGNING_KEY) == "b" * 64
    finally:
        log.removeHandler(cap)

    joined = "\n".join(cap.messages)
    assert SECRET_HEX not in joined
    assert "s.vault-token-secret" not in joined
    assert "s.vault-token-secret" not in repr(sm)
    assert "redacted" in repr(sm)


def test_file_adapter_prod_refused(tmp_path):
    wallet = tmp_path / "wallet.json"
    wallet.write_text(
        '{"address":"0xabc","private_key":"%s"}' % SECRET_HEX,
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="refused in production"):
        FileSecretAdapter(str(wallet), deployment_mode="prod")


def test_file_adapter_dev_loads_without_logging_key(tmp_path, caplog):
    wallet = tmp_path / "wallet.json"
    wallet.write_text(
        '{"address":"0xabc","private_key":"%s"}' % SECRET_HEX,
        encoding="utf-8",
    )
    sm = FileSecretAdapter(str(wallet), deployment_mode="dev")
    with caplog.at_level(logging.DEBUG):
        assert sm.get_secret(SECRET_NODE_WALLET_PRIVATE_KEY) == SECRET_HEX
    assert SECRET_HEX not in caplog.text
    assert SECRET_HEX not in repr(sm)


def test_secret_never_written_to_db_meta():
    """DoD: callers must not persist raw signing keys into DB meta."""
    sm = EnvK8sSecretAdapter(environ={"WALLET_PRIVATE_KEY": SECRET_HEX})
    db = _FakeDB()
    pk = sm.get_secret(SECRET_NODE_WALLET_PRIVATE_KEY)
    # Honest usage: address/meta only — never store pk.
    db.set_meta("signer_address", "0xdead")
    db.set_meta("secret_backend", "env")
    assert pk == SECRET_HEX
    blob = str(db.meta)
    assert SECRET_HEX not in blob
    assert "private_key" not in db.meta


def test_build_secret_manager_env_default():
    cfg = SimpleNamespace(secret_backend="env", deployment_mode="dev")
    sm = build_secret_manager(cfg)
    assert isinstance(sm, EnvK8sSecretAdapter)


def test_build_secret_manager_vault():
    cfg = SimpleNamespace(secret_backend="vault", deployment_mode="prod")
    sm = build_secret_manager(cfg)
    assert isinstance(sm, VaultKvSecretAdapter)


def test_prod_blocks_unknown_raw_env_passthrough():
    sm = EnvK8sSecretAdapter(
        environ={
            "DEPLOYMENT_MODE": "prod",
            "CUSTOM_UNKNOWN_SECRET": "leak-me",
        }
    )
    with pytest.raises(SecretNotFoundError):
        sm.get_secret("CUSTOM_UNKNOWN_SECRET")


def test_prod_raw_passthrough_requires_explicit_flag():
    sm = EnvK8sSecretAdapter(
        environ={
            "DEPLOYMENT_MODE": "prod",
            "ABS_SECRET_ALLOW_RAW": "1",
            "CUSTOM_UNKNOWN_SECRET": "ok-escape",
        }
    )
    assert sm.get_secret("CUSTOM_UNKNOWN_SECRET") == "ok-escape"
