#!/usr/bin/env python3
"""Smart account auth must fail closed without real verifiers."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from features.smart_accounts import AuthMethod, SessionPermission, SmartAccount, SmartAccountManager


def test_private_social_and_passkey_auth_fail_closed():
    account = SmartAccount("0x" + "a" * 40, "0x" + "b" * 40)
    account.add_auth_method(AuthMethod.PRIVATE_KEY, {"public_key": "0xpub"})
    account.add_auth_method(AuthMethod.SOCIAL, {"provider": "google"})
    account.add_auth_method(AuthMethod.PASSKEY, {"credential_id": "cred"})

    assert account.authenticate(AuthMethod.PRIVATE_KEY, "signed-message") is False
    assert account.authenticate(AuthMethod.SOCIAL, "provider-token") is False
    assert account.authenticate(AuthMethod.PASSKEY, {"assertion": "raw"}) is False


def test_session_key_auth_remains_bounded_by_validity():
    account = SmartAccount("0x" + "c" * 40, "0x" + "d" * 40)
    account.add_auth_method(AuthMethod.SESSION_KEY, {})
    session_key = account.create_session_key(
        [SessionPermission.TRANSFER],
        expires_in=60,
        max_uses=1,
    )
    key_id = session_key.split(".", 1)[0]

    assert account.authenticate(AuthMethod.SESSION_KEY, key_id) is False
    assert account.authenticate(AuthMethod.SESSION_KEY, session_key) is True
    account.session_keys[key_id].use()
    assert account.authenticate(AuthMethod.SESSION_KEY, session_key) is False


def test_manager_create_session_and_authenticate_fail_closed():
    manager = SmartAccountManager()
    created = manager.create_account("0x" + "e" * 40)
    address = created["address"]

    assert created["success"] is True
    assert manager.authenticate(address, "raw-private-key-signature", "private_key") is False

    session = manager.create_session_key(address, [SessionPermission.TRANSFER], max_uses=1)
    assert session["success"] is True
    assert manager.authenticate(address, session["key_id"], "session_key") is False
    assert manager.authenticate(address, session["session_key"], "session_key") is True
    manager.get_account(address).session_keys[session["key_id"]].use()
    assert manager.authenticate(address, session["session_key"], "session_key") is False


def test_smart_account_transaction_requires_execution_backend():
    account = SmartAccount("0x" + "f" * 40, "0x" + "1" * 40)
    account.add_auth_method(AuthMethod.SESSION_KEY, {})
    session_key = account.create_session_key(
        [SessionPermission.TRANSFER],
        expires_in=60,
        max_uses=1,
    )

    assert account.execute_transaction(
        "0x" + "2" * 40,
        1.0,
        auth_method=AuthMethod.SESSION_KEY,
        credential=session_key,
    ) is None


def test_smart_account_transaction_uses_real_executor_and_consumes_session():
    calls = []

    def executor(tx):
        calls.append(tx)
        return {"success": True, "tx_hash": "0xabc", **tx}

    account = SmartAccount(
        "0x" + "3" * 40,
        "0x" + "4" * 40,
        transaction_executor=executor,
    )
    account.add_auth_method(AuthMethod.SESSION_KEY, {})
    session_key = account.create_session_key(
        [SessionPermission.TRANSFER],
        expires_in=60,
        max_uses=1,
    )

    result = account.execute_transaction(
        "0x" + "5" * 40,
        2.0,
        auth_method=AuthMethod.SESSION_KEY,
        credential=session_key,
    )

    assert result["success"] is True
    assert result["tx_hash"] == "0xabc"
    assert calls[0]["from"] == account.address
    assert account.execute_transaction(
        "0x" + "5" * 40,
        2.0,
        auth_method=AuthMethod.SESSION_KEY,
        credential=session_key,
    ) is None
