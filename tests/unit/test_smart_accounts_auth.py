#!/usr/bin/env python3
"""Smart account auth must fail closed without real verifiers."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from features.smart_accounts import AuthMethod, SessionPermission, SmartAccount


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
    key_id = account.create_session_key(
        [SessionPermission.TRANSFER],
        expires_in=60,
        max_uses=1,
    )

    assert account.authenticate(AuthMethod.SESSION_KEY, key_id) is True
    account.session_keys[key_id].use()
    assert account.authenticate(AuthMethod.SESSION_KEY, key_id) is False
