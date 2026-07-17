# execution/state_root.py
"""
Canonical state root calculation for live Absolute account state.

The network currently commits to the SQLite account-state format used by
core.Blockchain. Keep this module as the single contract before moving more
state execution into Rust.
"""

import json
from typing import Any, Dict, List

from crypto import native


def _canonical_accounts_json(accounts: List[Dict[str, Any]]) -> str:
    """Encode DB account rows in deterministic address order for native input."""
    rows = sorted(accounts, key=lambda row: str(row.get("address", "")))
    return json.dumps(rows, sort_keys=True, separators=(",", ":"))


def compute_db_state_root(accounts: List[Dict[str, Any]]) -> str:
    """
    Compute the current 64-char state root from SQLite account rows.

    This preserves the historical payload:
    [{"a": address, "b": rounded_balance, "n": nonce, "c": code_hash, "s": storage_hash}]
    """
    return native.state_root_from_accounts_json(_canonical_accounts_json(accounts))


def compute_state_root_from_blobs(account_blobs: List[bytes]) -> str:
    """Fast path for RocksDB: hash account JSON blobs without Python row materialization."""
    from crypto import native

    if native.state_root_accumulator_available():
        return native.state_root_accumulator_root_from_blobs(account_blobs)
    return native.state_root_from_account_blobs(account_blobs)


def compute_state_engine_root(accounts: Dict[str, Any]) -> str:
    """
    In-memory StateEngine root (32-char legacy contract).

    Account ``balance`` fields are satoshi integers (v1.2.81+).
    """
    payload = {
        addr: {"balance_satoshi": int(acc.balance), "nonce": int(acc.nonce)}
        for addr, acc in accounts.items()
    }
    encoded = json.dumps(payload, sort_keys=True)
    return native.sha256_hex(encoded.encode())[:32]
