import json

from crypto import native
from execution.state_root import compute_db_state_root, compute_state_engine_root
from execution.state_engine import AccountState


def _accounts():
    return [
        {
            "address": "0x" + "b" * 40,
            "balance": 12.3456789012345,
            "nonce": 2,
            "code": "6001600055",
            "storage": '{"slot":"value"}',
        },
        {
            "address": "0x" + "a" * 40,
            "balance": 100.0,
            "nonce": 0,
            "code": None,
            "storage": None,
        },
        {
            "address": "0x" + "c" * 40,
            "balance": 0.0000000000014,
            "nonce": "7",
            "code": "",
            "storage": "",
        },
    ]


def test_db_state_root_matches_python_kernel():
    accounts = _accounts()
    expected = native._python_state_root_from_accounts(
        sorted(accounts, key=lambda row: row["address"])
    )

    assert compute_db_state_root(accounts) == expected
    assert len(compute_db_state_root(accounts)) == 64


def test_db_state_root_is_address_order_independent():
    accounts = _accounts()

    assert compute_db_state_root(accounts) == compute_db_state_root(list(reversed(accounts)))


def test_installed_abs_native_state_root_matches_python_kernel_when_available():
    if not native.native_available():
        return

    import abs_native

    accounts = sorted(_accounts(), key=lambda row: row["address"])
    encoded = json.dumps(accounts, sort_keys=True, separators=(",", ":"))

    assert abs_native.state_root_from_accounts_json(encoded) == native._python_state_root_from_accounts(
        accounts
    )


def test_state_root_from_account_blobs_matches_canonical():
    import json

    from crypto import native
    from execution.state_root import compute_db_state_root, compute_state_root_from_blobs

    accounts = _accounts()
    blobs = [
        json.dumps(row, sort_keys=True, separators=(",", ":")).encode("utf-8")
        for row in accounts
    ]
    assert compute_state_root_from_blobs(blobs) == compute_db_state_root(accounts)
    if native.native_available() and hasattr(__import__("abs_native"), "state_root_from_account_blobs"):
        assert native.state_root_from_account_blobs(blobs) == compute_db_state_root(accounts)


def test_legacy_state_engine_root_keeps_32_char_contract():
    accounts = {
        "alice": AccountState(balance=100, nonce=0),
        "bob": AccountState(balance=50, nonce=3),
    }

    root = compute_state_engine_root(accounts)
    assert len(root) == 32
    assert root == compute_state_engine_root(accounts)
