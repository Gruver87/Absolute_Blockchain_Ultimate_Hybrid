# crypto/native.py
"""
Native crypto facade for Absolute Blockchain.

This module routes hot deterministic crypto kernels to the PyO3/maturin
extension when it is installed. The Python path is kept byte-for-byte aligned
with the historical implementation so consensus behavior does not drift.
"""

import hashlib
import json
import os
from typing import Any, List, Optional


_DISABLE_NATIVE = os.getenv("ABS_DISABLE_NATIVE_CRYPTO", "").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
_REQUIRE_NATIVE = os.getenv("ABS_REQUIRE_NATIVE_CRYPTO", "").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

_native_error: Optional[BaseException] = None
_native = None

if not _DISABLE_NATIVE:
    try:
        import abs_native as _native  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on local wheel install
        _native_error = exc

if _REQUIRE_NATIVE and _native is None:
    raise RuntimeError(
        "ABS_REQUIRE_NATIVE_CRYPTO is enabled, but abs_native is not available"
    ) from _native_error


def native_available() -> bool:
    return _native is not None


def native_error() -> Optional[BaseException]:
    return _native_error


def native_crypto_status(required: bool = False) -> dict:
    status = {
        "available": native_available(),
        "required": bool(required or _REQUIRE_NATIVE),
        "self_test": False,
        "error": str(_native_error) if _native_error else "",
        "kernels": [
            "sha256",
            "merkle",
            "state_root",
            "secp256k1_verify",
        ],
    }
    if _native is None:
        return status
    try:
        ok = (
            sha256_hex(b"absolute")
            == "747355bdc2a224032fd405b1b9e8985bfca47e45b34668f7d0a70ee4789bd855"
        )
        ok = ok and merkle_root(["tx1", "tx2", "tx3"]) == _python_merkle_root_strings([
            "tx1",
            "tx2",
            "tx3",
        ])
        ok = ok and state_root_from_accounts_json("[]") == _python_state_root_from_accounts([])
        status["self_test"] = bool(ok)
    except Exception as exc:
        status["error"] = str(exc)
    return status


def _string_items(items: List[Any]) -> List[str]:
    return [str(item) for item in items]


def hash_data(data: Any) -> str:
    """Hash data exactly like the historical Merkle implementation."""
    return sha256_hex(str(data).encode())


def sha256_hex(data: bytes) -> str:
    if _native is not None:
        return _native.sha256_hex(data)
    return hashlib.sha256(data).hexdigest()


def double_sha256_hex(data: bytes) -> str:
    if _native is not None:
        return _native.double_sha256_hex(data)
    return hashlib.sha256(hashlib.sha256(data).digest()).hexdigest()


def merkle_root(items: List[Any]) -> str:
    string_items = _string_items(items)
    if _native is not None:
        return _native.merkle_root(string_items)
    return _python_merkle_root_strings(string_items)


def generate_proof(items: List[Any], target_index: int) -> List[str]:
    string_items = _string_items(items)
    if target_index < 0:
        return []
    if _native is not None:
        return _native.generate_proof(string_items, target_index)
    return _python_generate_proof_strings(string_items, target_index)


def verify_proof(item: Any, proof: List[str], expected_root: str, target_index: int) -> bool:
    if target_index < 0:
        return False
    item_str = str(item)
    if _native is not None:
        return bool(_native.verify_proof(item_str, proof, expected_root, target_index))
    return merkle_root_from_proof(item_str, proof, target_index) == expected_root


def merkle_root_from_proof(item: Any, proof: List[str], target_index: int) -> str:
    if target_index < 0:
        return hash_data(item)
    item_str = str(item)
    if _native is not None:
        return _native.merkle_root_from_proof(item_str, proof, target_index)
    return _python_merkle_root_from_proof_string(item_str, proof, target_index)


def state_root_from_accounts_json(accounts_json: str) -> str:
    if _native is not None:
        return _native.state_root_from_accounts_json(accounts_json)
    accounts = json.loads(accounts_json)
    return _python_state_root_from_accounts(accounts)


def verify_secp256k1_sha256(
    message: bytes, signature_der: bytes, public_key_xy: bytes
) -> Optional[bool]:
    if _native is None:
        return None
    try:
        return bool(_native.verify_secp256k1_sha256(
            message, signature_der, public_key_xy
        ))
    except Exception:
        return False


def verify_secp256k1_sha256_batch(
    items: List[tuple[bytes, bytes, bytes]]
) -> Optional[List[bool]]:
    if _native is None:
        return None
    try:
        return [
            bool(result)
            for result in _native.verify_secp256k1_sha256_batch(items)
        ]
    except Exception:
        return [False for _ in items]


def _python_merkle_root_strings(items: List[str]) -> str:
    if not items:
        return hash_data("empty")

    layer = [hash_data(item) for item in items]
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])

        new_layer = []
        for i in range(0, len(layer), 2):
            new_layer.append(hash_data(layer[i] + layer[i + 1]))
        layer = new_layer

    return layer[0]


def _python_generate_proof_strings(items: List[str], target_index: int) -> List[str]:
    if not items or target_index >= len(items):
        return []

    layer = [hash_data(item) for item in items]
    proof = []
    index = target_index

    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])

        sibling_index = index + 1 if index % 2 == 0 else index - 1
        if sibling_index < len(layer):
            proof.append(layer[sibling_index])

        new_layer = []
        for i in range(0, len(layer), 2):
            new_layer.append(hash_data(layer[i] + layer[i + 1]))
        layer = new_layer
        index //= 2

    return proof


def _python_merkle_root_from_proof_string(
    item: str, proof: List[str], target_index: int
) -> str:
    current_hash = hash_data(item)
    index = target_index

    for sibling_hash in proof:
        if index % 2 == 0:
            combined = current_hash + sibling_hash
        else:
            combined = sibling_hash + current_hash
        current_hash = hash_data(combined)
        index //= 2

    return current_hash


def _python_state_root_from_accounts(accounts: List[dict]) -> str:
    payload = []
    for row in accounts:
        code = row.get("code") or ""
        storage = row.get("storage") or "{}"
        code_hash = sha256_hex(code.encode()) if code else ""
        storage_hash = sha256_hex(storage.encode()) if storage else ""
        payload.append({
            "a": row["address"],
            "b": round(float(row["balance"]), 12),
            "n": int(row["nonce"]),
            "c": code_hash,
            "s": storage_hash,
        })
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256_hex(encoded.encode())
