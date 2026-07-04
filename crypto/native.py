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
            "sha256_batch",
            "hash_text",
            "hash_text_batch",
            "block_header_hash",
            "block_header_hash_batch",
            "transaction_hash",
            "transaction_hash_batch",
            "block_canonical_hash",
            "canonical_hash_json",
            "keccak256",
            "validate_imported_block_chain",
            "validate_peer_header_chain",
            "merkle",
            "state_root",
            "secp256k1_verify",
            "consensus_hash",
            "hash_chain_validation",
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
        ok = ok and keccak256_hex(b"") == (
            "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
        )
        status["self_test"] = bool(ok)
    except Exception as exc:
        status["error"] = str(exc)
    return status


def _string_items(items: List[Any]) -> List[str]:
    return [str(item) for item in items]


def hash_data(data: Any) -> str:
    """Hash data exactly like the historical Merkle implementation."""
    return sha256_hex(str(data).encode())


def hash_text(text: str) -> str:
    """SHA-256 of UTF-8 text through the native kernel when available."""
    if _native is not None and hasattr(_native, "hash_text"):
        return str(_native.hash_text(text))
    return sha256_hex(text.encode())


def hash_text_batch(items: List[str]) -> List[str]:
    """Batch SHA-256 of UTF-8 strings, preserving legacy per-item hashes."""
    if _native is not None and hasattr(_native, "hash_text_batch"):
        return [str(value) for value in _native.hash_text_batch(items)]
    return sha256_hex_batch([item.encode() for item in items])


def block_header_hash(
    number: int,
    parent_hash: str,
    proposer: str,
    state_root: str,
    tx_root: str,
    timestamp: int,
    extra_data: str = "",
) -> str:
    """Legacy consensus header hash (single header)."""
    if _native is not None and hasattr(_native, "block_header_hash"):
        return str(_native.block_header_hash(
            int(number),
            str(parent_hash),
            str(proposer),
            str(state_root),
            str(tx_root),
            int(timestamp),
            str(extra_data or ""),
        ))
    return hash_text(
        f"{number}{parent_hash}{proposer}{state_root}{tx_root}{timestamp}{extra_data or ''}"
    )


def block_header_hash_batch(
    headers: List[tuple[int, str, str, str, str, int, str]],
) -> List[str]:
    """Legacy consensus header hash for many headers in one native call."""
    if _native is not None and hasattr(_native, "block_header_hash_batch"):
        payload = [
            (
                int(number),
                str(parent_hash),
                str(proposer),
                str(state_root),
                str(tx_root),
                int(timestamp),
                str(extra_data or ""),
            )
            for number, parent_hash, proposer, state_root, tx_root, timestamp, extra_data in headers
        ]
        return [str(value) for value in _native.block_header_hash_batch(payload)]
    return [
        block_header_hash(number, parent_hash, proposer, state_root, tx_root, timestamp, extra_data)
        for number, parent_hash, proposer, state_root, tx_root, timestamp, extra_data in headers
    ]


def transaction_hash(
    from_addr: str,
    to_addr: str,
    value: float,
    nonce: int,
    gas: int,
    data: str,
    timestamp: int,
) -> str:
    """Legacy raw transaction hash used by consensus and signing."""
    if _native is not None and hasattr(_native, "transaction_hash"):
        return str(_native.transaction_hash(
            str(from_addr),
            str(to_addr),
            float(value),
            int(nonce),
            int(gas),
            str(data or ""),
            int(timestamp),
        ))
    raw = f"{from_addr}{to_addr}{value}{nonce}{gas}{data}{timestamp}"
    return hash_text(raw)


def transaction_hash_batch(
    transactions: List[tuple[str, str, float, int, int, str, int]],
) -> List[str]:
    if _native is not None and hasattr(_native, "transaction_hash_batch"):
        payload = [
            (
                str(from_addr),
                str(to_addr),
                float(value),
                int(nonce),
                int(gas),
                str(data or ""),
                int(timestamp),
            )
            for from_addr, to_addr, value, nonce, gas, data, timestamp in transactions
        ]
        return [str(value) for value in _native.transaction_hash_batch(payload)]
    return [
        transaction_hash(from_addr, to_addr, value, nonce, gas, data, timestamp)
        for from_addr, to_addr, value, nonce, gas, data, timestamp in transactions
    ]


def _block_dict_for_canonical_hash(block: dict) -> dict:
    block_copy = dict(block)
    txs = list(block_copy.get("transactions") or [])
    if txs:
        block_copy["transactions"] = sorted(
            txs,
            key=lambda row: str((row or {}).get("hash", "")),
        )
    return block_copy


def block_canonical_hash(block: dict) -> str:
    """Deterministic block hash via CanonicalSerializer rules."""
    block_copy = _block_dict_for_canonical_hash(block)
    encoded = json.dumps(block_copy, separators=(",", ":"), ensure_ascii=False)
    if _native is not None and hasattr(_native, "block_canonical_hash_json"):
        return str(_native.block_canonical_hash_json(encoded))
    return hash_text(_python_canonical_serialize(block_copy))


def canonical_hash_json(obj_json: str) -> str:
    """Hash a JSON object using canonical float-to-satoshi rules."""
    if _native is not None and hasattr(_native, "canonical_hash_json"):
        return str(_native.canonical_hash_json(obj_json))
    value = json.loads(obj_json)
    return hash_text(_python_canonical_serialize(value))


def _python_canonical_serialize(obj: Any) -> str:
    return json.dumps(
        _python_canonicalize(obj),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _python_canonicalize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            key: _python_canonicalize(value)
            for key, value in sorted(obj.items())
        }
    if isinstance(obj, list):
        return [_python_canonicalize(item) for item in obj]
    if isinstance(obj, float):
        return int(obj * 1_000_000)
    return obj


def keccak256_hex(data: bytes) -> str:
    """Ethereum-compatible Keccak-256."""
    if _native is not None and hasattr(_native, "keccak256_hex"):
        return str(_native.keccak256_hex(data))
    return hashlib.sha3_256(data).hexdigest()


def keccak256_digest(data: bytes) -> bytes:
    return bytes.fromhex(keccak256_hex(data))


def validate_imported_block_chain(
    blocks: List[dict],
    expected_parent_hash: str = "",
    start_height: int = 0,
) -> bool:
    """Fail-closed P2P sync gate: parent links + canonical block hash."""
    if not blocks:
        return True
    payloads = [
        json.dumps(block, separators=(",", ":"), ensure_ascii=False)
        for block in blocks
    ]
    if _native is not None and hasattr(_native, "validate_imported_block_chain"):
        return bool(_native.validate_imported_block_chain(
            payloads,
            str(expected_parent_hash or ""),
            int(start_height),
        ))

    previous_hash = str(expected_parent_hash or "")
    previous_height = int(start_height)
    for block in blocks:
        height = int(block.get("height", block.get("number", 0)) or 0)
        block_hash = str(block.get("hash", block.get("block_hash", "")) or "")
        parent_hash = str(block.get("parent_hash", block.get("parent", "")) or "")
        if not block_hash or height != previous_height + 1:
            return False
        if previous_hash and parent_hash != previous_hash:
            return False
        if block_canonical_hash(block) != block_hash:
            return False
        previous_hash = block_hash
        previous_height = height
    return True


def validate_peer_header_chain(
    headers: List[tuple[int, str, str, str, str, str, int, str]],
    expected_parent_hash: str = "",
    start_height: int = 0,
) -> bool:
    """Validate contiguous peer headers and recomputed header hashes."""
    if not headers:
        return True
    if _native is not None and hasattr(_native, "validate_peer_header_chain"):
        payload = [
            (
                int(number),
                str(block_hash),
                str(parent_hash),
                str(proposer),
                str(state_root),
                str(tx_root),
                int(timestamp),
                str(extra_data or ""),
            )
            for number, block_hash, parent_hash, proposer, state_root, tx_root, timestamp, extra_data in headers
        ]
        return bool(_native.validate_peer_header_chain(
            payload,
            str(expected_parent_hash or ""),
            int(start_height),
        ))

    previous_hash = str(expected_parent_hash or "")
    previous_height = int(start_height)
    for number, block_hash, parent_hash, proposer, state_root, tx_root, timestamp, extra_data in headers:
        if not block_hash or int(number) != previous_height + 1:
            return False
        if previous_hash and parent_hash != previous_hash:
            return False
        if block_header_hash(
            number, parent_hash, proposer, state_root, tx_root, timestamp, extra_data
        ) != block_hash:
            return False
        previous_hash = block_hash
        previous_height = int(number)
    return True


def sha256_hex(data: bytes) -> str:
    if _native is not None:
        return _native.sha256_hex(data)
    return hashlib.sha256(data).hexdigest()


def sha256_hex_batch(items: List[bytes]) -> List[str]:
    if _native is not None and hasattr(_native, "sha256_hex_batch"):
        return [str(value) for value in _native.sha256_hex_batch(items)]
    return [hashlib.sha256(item).hexdigest() for item in items]


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


def validate_hash_chain(
    headers: List[tuple[int, str, str]],
    expected_parent_hash: str = "",
    start_height: int = 0,
) -> bool:
    """Validate contiguous (height, hash, parent_hash) links."""
    normalized = [
        (int(height), str(block_hash), str(parent_hash))
        for height, block_hash, parent_hash in headers
    ]
    if _native is not None and hasattr(_native, "validate_hash_chain"):
        return bool(_native.validate_hash_chain(
            normalized,
            str(expected_parent_hash or ""),
            int(start_height),
        ))
    previous_hash = str(expected_parent_hash or "")
    previous_height = int(start_height)
    for height, block_hash, parent_hash in normalized:
        if not block_hash or height != previous_height + 1:
            return False
        if previous_hash and parent_hash != previous_hash:
            return False
        previous_hash = block_hash
        previous_height = height
    return True


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
