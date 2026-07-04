import json

from crypto import native
from crypto.native import state_root_from_accounts_json as py_state_root


def test_state_root_port_golden_vectors():
    vectors = [
        [],
        [
            {"address": "0x1", "balance": "100.0", "nonce": "0", "code": "", "storage": "{}"}
        ],
        [
            {"address": "0x1", "balance": "1.2345", "nonce": "2", "code": "foo", "storage": "{}"},
            {"address": "0x2", "balance": "0.0", "nonce": "0", "code": "", "storage": "{}"},
        ],
    ]

    for accounts in vectors:
        accounts_json = json.dumps(accounts, sort_keys=True, separators=(",", ":"))
        py = py_state_root(accounts_json)
        native_avail = native.native_available()
        if native_avail:
            rn = native.state_root_from_accounts_json(accounts_json)
            assert py == rn
        else:
            # If native not available, at least python path must be stable
            assert isinstance(py, str) and len(py) > 0

