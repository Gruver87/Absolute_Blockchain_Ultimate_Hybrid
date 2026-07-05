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
    return native.state_root_from_account_blobs(account_blobs)


def compute_state_engine_root(accounts: Dict[str, Any]) -> str:
    """
    Legacy in-memory StateEngine root.

    StateEngine historically exposes a 32-char root, so this helper keeps that
    compatibility until the in-memory engine is fully aligned with SQLite state.
    """
    payload = {
        addr: {"balance": acc.balance, "nonce": acc.nonce}
        for addr, acc in accounts.items()
    }
    encoded = json.dumps(payload, sort_keys=True)
    return native.sha256_hex(encoded.encode())[:32]
