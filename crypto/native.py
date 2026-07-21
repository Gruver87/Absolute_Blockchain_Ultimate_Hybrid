# crypto/native.py
"""
Native crypto facade for Absolute Blockchain.

This module routes hot deterministic crypto kernels to the PyO3/maturin
extension when it is installed. The Python path is kept byte-for-byte aligned
with the historical implementation so consensus behavior does not drift.
"""

import hashlib
import json
import math
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

_NATIVE_REQUIRED_MSG = (
    "ABS_REQUIRE_NATIVE_CRYPTO is enabled: abs_native kernel required "
    "(pip install -e native/abs_native)"
)


def _require_native_kernel(kernel: str = "abs_native") -> None:
    if _REQUIRE_NATIVE and _native is None:
        raise RuntimeError(_NATIVE_REQUIRED_MSG)


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
            "block_canonical_hash_batch",
            "canonical_hash_json",
            "keccak256",
            "keccak256_digest_batch",
            "evm_u256",
            "evm_u256_cmp",
            "evm_u256_sgt",
            "evm_memory",
            "evm_read_push",
            "evm_jumpdest",
            "evm_call_gas",
            "evm_stack",
            "evm_memory_slice",
            "evm_bytecode_scan",
            "evm_keccak256_memory",
            "evm_pure_runner",
            "evm_run_until_halt",
            "evm_deploy_address",
            "evm_create2_eip1014",
            "validate_imported_block_chain",
            "validate_peer_header_chain",
            "consensus_stake_weighted_proposer",
            "consensus_fisher_yates_committee",
            "validator_selection_proposer",
            "validator_selection_proposer_weighted",
            "validator_selection_committee",
            "validator_selection_shuffle",
            "state_engine_root_from_accounts_json",
            "parse_p2p_wire_line",
            "encode_p2p_wire_message",
            "hash_sorted_json",
            "verify_attestation_secp256k1",
            "validate_p2p_status_payload",
            "validate_p2p_attestation_payload",
            "validate_p2p_block_announce",
            "validate_p2p_state_root_request",
            "validate_p2p_state_root_response",
            "validate_p2p_handshake_payload",
            "validate_p2p_get_blocks_payload",
            "validate_p2p_wire_tx",
            "validate_p2p_mempool_batch",
            "amount_to_satoshi",
            "amount_apply_delta_satoshi",
            "state_engine_apply_transactions",
            "plan_transfer_fees",
            "can_afford_transfer",
            "merkle",
            "state_root",
            "secp256k1_verify",
            "consensus_hash",
            "hash_chain_validation",
            "rlp_encode",
            "rlp_decode",
            "rlp_decode_single",
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
        if _native is not None and hasattr(_native, "rlp_encode"):
            from crypto.rlp import decode_single, encode

            sample = [0, 1, 255, 256]
            ok = ok and decode_single(encode(sample)) == [
                b"",
                b"\x01",
                b"\xff",
                b"\x01\x00",
            ]
        if _native is not None and hasattr(_native, "evm_run_until_halt"):
            bc = bytes([0x60, 0x02, 0x60, 0x03, 0x01, 0x00])
            table = evm_build_jumpdest_table(bc)
            seg = evm_run_until_halt(
                bc,
                0,
                1_000_000,
                0,
                [],
                bytearray(),
                table,
                b"",
                b"",
                {
                    "address": 0,
                    "caller": 0,
                    "origin": 0,
                    "value": 0,
                    "timestamp": 0,
                    "block_number": 0,
                    "chain_id": 0,
                },
            )
            ok = ok and seg.get("stop_reason") == "halt" and seg.get("stack") == [5]
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
    _require_native_kernel("block_canonical_hash")
    return hash_text(_python_canonical_serialize(block_copy))


def block_canonical_hash_batch(blocks: List[dict]) -> List[str]:
    """Batch canonical block hash for sync/import hot paths."""
    payloads = [
        json.dumps(_block_dict_for_canonical_hash(block), separators=(",", ":"), ensure_ascii=False)
        for block in blocks
    ]
    if _native is not None and hasattr(_native, "block_canonical_hash_batch"):
        return [str(value) for value in _native.block_canonical_hash_batch(payloads)]
    return [block_canonical_hash(block) for block in blocks]


def canonical_hash_json(obj_json: str) -> str:
    """Hash a JSON object using canonical float-to-satoshi rules."""
    if _native is not None and hasattr(_native, "canonical_hash_json"):
        return str(_native.canonical_hash_json(obj_json))
    _require_native_kernel("canonical_hash_json")
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
    if _REQUIRE_NATIVE:
        raise RuntimeError(_NATIVE_REQUIRED_MSG)
    try:
        from Crypto.Hash import keccak as _keccak

        digest = _keccak.new(digest_bits=256)
        digest.update(data)
        return digest.hexdigest()
    except ImportError:
        raise RuntimeError(
            "keccak256_hex requires abs_native (pip install -e native/abs_native) "
            "or pycryptodome; hashlib.sha3_256 is NOT Ethereum Keccak"
        )


def keccak256_digest(data: bytes) -> bytes:
    if _native is not None and hasattr(_native, "keccak256_digest"):
        return bytes(_native.keccak256_digest(data))
    return bytes.fromhex(keccak256_hex(data))


def keccak256_digest_batch(items: List[bytes]) -> List[bytes]:
    if _native is not None and hasattr(_native, "keccak256_digest_batch"):
        return [bytes(digest) for digest in _native.keccak256_digest_batch([bytes(item) for item in items])]
    return [keccak256_digest(item) for item in items]


def recover_eth_address_keccak(prehash: bytes, r: bytes, s: bytes, rec_id: int) -> str:
    if _native is not None and hasattr(_native, "recover_eth_address_keccak"):
        return str(_native.recover_eth_address_keccak(prehash, r, s, int(rec_id)))
    raise RuntimeError("recover_eth_address_keccak requires abs_native")


def pubkey_to_eth_address(public_key: bytes) -> str:
    """Keccak-256 Ethereum address from secp256k1 public key bytes."""
    if _native is not None and hasattr(_native, "pubkey_to_eth_address"):
        return str(_native.pubkey_to_eth_address(public_key))
    if _REQUIRE_NATIVE:
        raise RuntimeError(_NATIVE_REQUIRED_MSG)
    pk = public_key[1:] if len(public_key) == 65 and public_key[0] == 0x04 else public_key
    if len(pk) != 64:
        raise ValueError("public_key must be 64 bytes uncompressed or 65 with 0x04 prefix")
    digest = keccak256_digest(pk)
    return "0x" + digest[-20:].hex()


EVM_U256_MASK = (1 << 256) - 1


def _evm_u256_bytes(value: int) -> bytes:
    return int(value & EVM_U256_MASK).to_bytes(32, "big")


def _evm_u256_int(value: bytes) -> int:
    return int.from_bytes(value, "big")


def _evm_u256_binop(name: str, left: int, right: int) -> int:
    if _native is not None and hasattr(_native, name):
        result = getattr(_native, name)(_evm_u256_bytes(left), _evm_u256_bytes(right))
        return _evm_u256_int(bytes(result))
    left &= EVM_U256_MASK
    right &= EVM_U256_MASK
    if name == "evm_u256_add":
        return (left + right) & EVM_U256_MASK
    if name == "evm_u256_mul":
        return (left * right) & EVM_U256_MASK
    if name == "evm_u256_sub":
        return (left - right) & EVM_U256_MASK
    if name == "evm_u256_div":
        return 0 if right == 0 else left // right
    if name == "evm_u256_mod":
        return 0 if right == 0 else left % right
    if name == "evm_u256_and":
        return left & right
    if name == "evm_u256_or":
        return left | right
    if name == "evm_u256_xor":
        return left ^ right
    raise ValueError(f"unsupported EVM binop: {name}")


def evm_u256_add(left: int, right: int) -> int:
    return _evm_u256_binop("evm_u256_add", left, right)


def evm_u256_mul(left: int, right: int) -> int:
    return _evm_u256_binop("evm_u256_mul", left, right)


def evm_u256_sub(left: int, right: int) -> int:
    return _evm_u256_binop("evm_u256_sub", left, right)


def evm_u256_div(left: int, right: int) -> int:
    return _evm_u256_binop("evm_u256_div", left, right)


def evm_u256_mod(left: int, right: int) -> int:
    return _evm_u256_binop("evm_u256_mod", left, right)


def evm_u256_and(left: int, right: int) -> int:
    return _evm_u256_binop("evm_u256_and", left, right)


def evm_u256_or(left: int, right: int) -> int:
    return _evm_u256_binop("evm_u256_or", left, right)


def evm_u256_xor(left: int, right: int) -> int:
    return _evm_u256_binop("evm_u256_xor", left, right)


def evm_u256_not(value: int) -> int:
    value &= EVM_U256_MASK
    if _native is not None and hasattr(_native, "evm_u256_not"):
        return _evm_u256_int(bytes(_native.evm_u256_not(_evm_u256_bytes(value))))
    return (~value) & EVM_U256_MASK


def evm_u256_shl(value: int, shift: int) -> int:
    value &= EVM_U256_MASK
    shift = int(shift) & EVM_U256_MASK
    if _native is not None and hasattr(_native, "evm_u256_shl"):
        return _evm_u256_int(bytes(_native.evm_u256_shl(_evm_u256_bytes(value), int(shift))))
    return (value << shift) & EVM_U256_MASK


def evm_u256_shr(value: int, shift: int) -> int:
    value &= EVM_U256_MASK
    shift = int(shift) & EVM_U256_MASK
    if _native is not None and hasattr(_native, "evm_u256_shr"):
        return _evm_u256_int(bytes(_native.evm_u256_shr(_evm_u256_bytes(value), int(shift))))
    return value >> shift


def evm_u256_slt(left: int, right: int) -> int:
    if _native is not None and hasattr(_native, "evm_u256_slt"):
        return _evm_u256_int(
            bytes(_native.evm_u256_slt(_evm_u256_bytes(left), _evm_u256_bytes(right)))
        )
    left &= EVM_U256_MASK
    right &= EVM_U256_MASK
    sign = 1 << 255
    left_neg = left >= sign
    right_neg = right >= sign
    if left_neg == right_neg:
        truthy = left < right
    else:
        truthy = left_neg
    return 1 if truthy else 0


def evm_u256_sgt(left: int, right: int) -> int:
    if _native is not None and hasattr(_native, "evm_u256_sgt"):
        return _evm_u256_int(
            bytes(_native.evm_u256_sgt(_evm_u256_bytes(left), _evm_u256_bytes(right)))
        )
    return evm_u256_slt(right, left)


def evm_u256_sar(value: int, shift: int) -> int:
    shift = int(shift) & EVM_U256_MASK
    if _native is not None and hasattr(_native, "evm_u256_sar"):
        return _evm_u256_int(bytes(_native.evm_u256_sar(_evm_u256_bytes(value), int(shift))))
    value &= EVM_U256_MASK
    if shift >= 256:
        return EVM_U256_MASK if value >= (1 << 255) else 0
    if value >= (1 << 255):
        mask = EVM_U256_MASK << (256 - shift) & EVM_U256_MASK
        return (value >> shift) | mask
    return value >> shift


def _evm_u256_cmp(name: str, left: int, right: int = 0) -> int:
    if name == "evm_u256_iszero":
        if _native is not None and hasattr(_native, name):
            result = getattr(_native, name)(_evm_u256_bytes(left))
            return _evm_u256_int(bytes(result))
        return 1 if (left & EVM_U256_MASK) == 0 else 0
    if _native is not None and hasattr(_native, name):
        result = getattr(_native, name)(_evm_u256_bytes(left), _evm_u256_bytes(right))
        return _evm_u256_int(bytes(result))
    left &= EVM_U256_MASK
    right &= EVM_U256_MASK
    if name == "evm_u256_eq":
        return 1 if left == right else 0
    if name == "evm_u256_lt":
        return 1 if left < right else 0
    if name == "evm_u256_gt":
        return 1 if left > right else 0
    raise ValueError(f"unsupported EVM cmp: {name}")


def evm_u256_eq(left: int, right: int) -> int:
    return _evm_u256_cmp("evm_u256_eq", left, right)


def evm_u256_lt(left: int, right: int) -> int:
    return _evm_u256_cmp("evm_u256_lt", left, right)


def evm_u256_gt(left: int, right: int) -> int:
    return _evm_u256_cmp("evm_u256_gt", left, right)


def evm_u256_iszero(value: int) -> int:
    return _evm_u256_cmp("evm_u256_iszero", value)


def evm_u256_byte(index: int, word: int) -> int:
    index = int(index) & EVM_U256_MASK
    word &= EVM_U256_MASK
    if _native is not None and hasattr(_native, "evm_u256_byte"):
        return _evm_u256_int(bytes(_native.evm_u256_byte(int(index), _evm_u256_bytes(word))))
    if index >= 32:
        return 0
    return (word >> (8 * (31 - index))) & 0xFF


def evm_memory_read_word(memory: bytes, offset: int) -> int:
    offset = int(offset)
    if _native is not None and hasattr(_native, "evm_memory_read_word"):
        return _evm_u256_int(bytes(_native.evm_memory_read_word(memory, offset)))
    end = offset + 32
    chunk = memory[offset:end] if offset < len(memory) else b""
    if len(chunk) < 32:
        chunk = chunk + (b"\x00" * (32 - len(chunk)))
    return int.from_bytes(chunk, "big")


def evm_calldataload(calldata: bytes, offset: int) -> int:
    offset = int(offset)
    if _native is not None and hasattr(_native, "evm_calldataload"):
        return _evm_u256_int(bytes(_native.evm_calldataload(calldata, offset)))
    end = offset + 32
    chunk = calldata[offset:end] if offset < len(calldata) else b""
    if len(chunk) < 32:
        chunk = chunk + (b"\x00" * (32 - len(chunk)))
    return int.from_bytes(chunk, "big")


def _evm_i256_to_signed(value: int) -> int:
    value &= EVM_U256_MASK
    if value >= (1 << 255):
        return value - (1 << 256)
    return value


def _evm_i256_from_signed(value: int) -> int:
    return int(value) & EVM_U256_MASK


def _evm_u256_native_call(name: str, *args: int) -> int:
    if _native is not None and hasattr(_native, name):
        packed = [_evm_u256_bytes(arg) for arg in args]
        if len(packed) == 1:
            result = getattr(_native, name)(packed[0])
        elif len(packed) == 2:
            result = getattr(_native, name)(packed[0], packed[1])
        else:
            result = getattr(_native, name)(packed[0], packed[1], packed[2])
        return _evm_u256_int(bytes(result))
    raise ValueError(f"unsupported native call: {name}")


def evm_u256_sdiv(left: int, right: int) -> int:
    left &= EVM_U256_MASK
    right &= EVM_U256_MASK
    if _native is not None and hasattr(_native, "evm_u256_sdiv"):
        return _evm_u256_native_call("evm_u256_sdiv", left, right)
    if right == 0:
        return 0
    if left == (1 << 255) and right == EVM_U256_MASK:
        return left
    return _evm_i256_from_signed(int(_evm_i256_to_signed(left) / _evm_i256_to_signed(right)))


def evm_u256_smod(left: int, right: int) -> int:
    left &= EVM_U256_MASK
    right &= EVM_U256_MASK
    if _native is not None and hasattr(_native, "evm_u256_smod"):
        return _evm_u256_native_call("evm_u256_smod", left, right)
    if right == 0:
        return 0
    left_s = _evm_i256_to_signed(left)
    right_s = abs(_evm_i256_to_signed(right))
    return _evm_i256_from_signed(int(math.copysign(abs(left_s) % right_s, left_s)))


def evm_u256_addmod(left: int, right: int, modulo: int) -> int:
    left &= EVM_U256_MASK
    right &= EVM_U256_MASK
    modulo &= EVM_U256_MASK
    if _native is not None and hasattr(_native, "evm_u256_addmod"):
        return _evm_u256_native_call("evm_u256_addmod", left, right, modulo)
    if modulo == 0:
        return 0
    return (left + right) % modulo


def evm_u256_mulmod(left: int, right: int, modulo: int) -> int:
    left &= EVM_U256_MASK
    right &= EVM_U256_MASK
    modulo &= EVM_U256_MASK
    if _native is not None and hasattr(_native, "evm_u256_mulmod"):
        return _evm_u256_native_call("evm_u256_mulmod", left, right, modulo)
    if modulo == 0:
        return 0
    return (left * right) % modulo


def evm_u256_exp(base: int, exponent: int) -> int:
    base &= EVM_U256_MASK
    exponent &= EVM_U256_MASK
    if _native is not None and hasattr(_native, "evm_u256_exp"):
        return _evm_u256_native_call("evm_u256_exp", base, exponent)
    if exponent == 0:
        return 0 if base == 0 else 1
    result = 1
    b = base
    e = exponent
    while e:
        if e & 1:
            result = (result * b) & EVM_U256_MASK
        b = (b * b) & EVM_U256_MASK
        e >>= 1
    return result


def evm_u256_signextend(index: int, word: int) -> int:
    index = int(index) & EVM_U256_MASK
    word &= EVM_U256_MASK
    if _native is not None and hasattr(_native, "evm_u256_signextend"):
        result = _native.evm_u256_signextend(int(index), _evm_u256_bytes(word))
        return _evm_u256_int(bytes(result))
    if index >= 32:
        return word
    bit = 8 * index + 7
    lower_mask = (1 << (bit + 1)) - 1
    if word & (1 << bit):
        return word | (~lower_mask & EVM_U256_MASK)
    return word & lower_mask


def evm_memory_write_word(memory: bytearray, offset: int, value: int) -> None:
    offset = int(offset)
    word = _evm_u256_bytes(value)
    if _native is not None and hasattr(_native, "evm_memory_write_word"):
        _native.evm_memory_write_word(memory, offset, word)
        return
    for i in range(32):
        idx = offset + i
        if idx < len(memory):
            memory[idx] = word[i]


def evm_memory_write_byte(memory: bytearray, offset: int, value: int) -> None:
    offset = int(offset)
    if _native is not None and hasattr(_native, "evm_memory_write_byte"):
        _native.evm_memory_write_byte(memory, offset, int(value) & 0xFF)
        return
    if offset < len(memory):
        memory[offset] = int(value) & 0xFF


def evm_read_push(bytecode: bytes, pc: int, size: int) -> int:
    pc = int(pc)
    size = int(size)
    if _native is not None and hasattr(_native, "evm_read_push"):
        return _evm_u256_int(bytes(_native.evm_read_push(bytecode, pc, size)))
    start = pc + 1
    end = min(start + size, len(bytecode))
    chunk = bytecode[start:end]
    if len(chunk) < size:
        chunk = chunk + (b"\x00" * (size - len(chunk)))
    return int.from_bytes(chunk, "big")


def evm_build_jumpdest_table(bytecode: bytes) -> bytes:
    if _native is not None and hasattr(_native, "evm_build_jumpdest_table"):
        return bytes(_native.evm_build_jumpdest_table(bytecode))
    table = bytearray((len(bytecode) + 7) // 8)
    pc = 0
    while pc < len(bytecode):
        op = bytecode[pc]
        if op == 0x5B:
            table[pc // 8] |= 1 << (pc % 8)
        if 0x60 <= op <= 0x7F:
            pc += 1 + (op - 0x5F)
        else:
            pc += 1
    return bytes(table)


def evm_is_jumpdest(table: bytes, dest: int, bytecode_len: int) -> bool:
    dest = int(dest)
    bytecode_len = int(bytecode_len)
    if dest < 0 or dest >= bytecode_len:
        return False
    if _native is not None and hasattr(_native, "evm_is_jumpdest"):
        return bool(_native.evm_is_jumpdest(table, dest, bytecode_len))
    return bool((table[dest // 8] >> (dest % 8)) & 1)


def evm_word_to_address(word: int) -> str:
    word &= EVM_U256_MASK
    if _native is not None and hasattr(_native, "evm_word_to_address"):
        return str(_native.evm_word_to_address(_evm_u256_bytes(word)))
    return "0x" + format(word & ((1 << 160) - 1), "040x")


def evm_call_gas_cap(remaining: int, requested: int) -> int:
    remaining = max(0, int(remaining))
    requested = max(0, int(requested))
    if _native is not None and hasattr(_native, "evm_call_gas_cap"):
        return int(_native.evm_call_gas_cap(remaining, requested))
    cap = remaining * 63 // 64
    if requested <= 0:
        return cap
    return min(requested, cap)


def evm_memory_slice(memory: bytes, offset: int, size: int) -> bytes:
    offset = int(offset)
    size = int(size)
    if _native is not None and hasattr(_native, "evm_memory_slice"):
        return bytes(_native.evm_memory_slice(memory, offset, size))
    end = offset + size
    chunk = memory[offset:end] if offset < len(memory) else b""
    if len(chunk) < size:
        chunk = chunk + (b"\x00" * (size - len(chunk)))
    return bytes(chunk)


def evm_stack_dup(stack: list, depth: int) -> None:
    depth = int(depth)
    if _native is not None and hasattr(_native, "evm_stack_dup"):
        try:
            _native.evm_stack_dup(stack, depth)
        except Exception as exc:
            raise RuntimeError("stack underflow") from exc
        return
    if depth <= 0 or depth > len(stack):
        raise RuntimeError("stack underflow")
    stack.append(stack[-depth])


def evm_stack_swap(stack: list, depth: int) -> None:
    depth = int(depth)
    if _native is not None and hasattr(_native, "evm_stack_swap"):
        try:
            _native.evm_stack_swap(stack, depth)
        except Exception as exc:
            raise RuntimeError("stack underflow") from exc
        return
    if depth <= 0 or depth >= len(stack):
        raise RuntimeError("stack underflow")
    stack[-1], stack[-1 - depth] = stack[-1 - depth], stack[-1]


def evm_scan_bytecode(bytecode: bytes):
    if _native is not None and hasattr(_native, "evm_scan_bytecode"):
        return [(int(pc), int(op)) for pc, op in _native.evm_scan_bytecode(bytecode)]
    issues = []
    pc = 0
    while pc < len(bytecode):
        op = bytecode[pc]
        if not _evm_opcode_supported_python(op):
            issues.append((pc, op))
        if 0x60 <= op <= 0x7F:
            pc += 1 + (op - 0x5F)
        else:
            pc += 1
    return issues


def _evm_opcode_supported_python(op: int) -> bool:
    if 0x60 <= op <= 0x7F or 0x80 <= op <= 0x8F or 0x90 <= op <= 0x9F or 0xA0 <= op <= 0xA4:
        return True
    return op in _EVM_SUPPORTED_SINGLE_OPCODES


_EVM_SUPPORTED_SINGLE_OPCODES = {
    0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B,
    0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1D,
    0x20,
    0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A,
    0x3B, 0x3C, 0x3D, 0x3E, 0x3F, 0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48,
    0x49, 0x4A,
    0x50, 0x51, 0x52, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5A, 0x5B,
    0x5C, 0x5D, 0x5E, 0x5F,
    0xA0, 0xA1, 0xA2, 0xA3, 0xA4,
    0xF0, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xFA, 0xFD, 0xFE, 0xFF,
}


def evm_gas_remaining(gas_limit: int, gas_used: int) -> int:
    gas_limit = max(0, int(gas_limit))
    gas_used = max(0, int(gas_used))
    if _native is not None and hasattr(_native, "evm_gas_remaining"):
        return int(_native.evm_gas_remaining(gas_limit, gas_used))
    return max(0, gas_limit - gas_used)


_EVM_HOST_OPCODES = frozenset({
    0xF0, 0xF1, 0xF2, 0xF4, 0xF5, 0xFA, 0xFF,
    *range(0xA0, 0xA5),
})

_EVM_BRIDGE_OPCODES = frozenset({0x31, 0x3B, 0x3C, 0x3F, 0x40})


def evm_host_context_from_evm(ctx) -> dict:
    """Build static host context dict for native pure runner."""
    host = {
        "address": ctx.addr_int(ctx.address),
        "caller": ctx.addr_int(ctx.caller),
        "origin": ctx.addr_int(ctx.origin),
        "value": int(ctx.value),
        "timestamp": int(ctx.timestamp),
        "block_number": int(ctx.block_number),
        "chain_id": int(ctx.chain_id),
        "base_fee": int(getattr(ctx, "base_fee", 0) or 0),
        "gas_price": int(getattr(ctx, "gas_price", 0) or 0),
        "difficulty": int(getattr(ctx, "difficulty", 0) or 0),
        "coinbase": ctx.addr_int(getattr(ctx, "coinbase", "") or ""),
        "blob_base_fee": int(getattr(ctx, "blob_base_fee", 0) or 0),
        "blob_hashes": [
            int(h) & ((1 << 256) - 1)
            for h in (getattr(ctx, "blob_hashes", None) or [])
        ],
    }
    hooks = {}
    if ctx.balance_of:
        hooks["balance"] = ctx.balance_of
    if ctx.code_size_of:
        hooks["code_size"] = ctx.code_size_of
    if ctx.code_copy_of:
        hooks["code_copy"] = ctx.code_copy_of
    if ctx.code_size_of or ctx.code_copy_of:
        def _code_hash(addr):
            size = int(ctx.code_size_of(addr)) if ctx.code_size_of else 0
            if size <= 0:
                return 0
            code = ctx.code_copy_of(addr, 0, size) if ctx.code_copy_of else b""
            if not code:
                return 0
            return int.from_bytes(keccak256_digest(code), "big")
        hooks["code_hash"] = _code_hash
    if ctx.block_hash_of:
        hooks["block_hash"] = ctx.block_hash_of
    if ctx.emit_log:
        hooks["emit_log"] = ctx.emit_log
    if hooks:
        host["bridge_hooks"] = hooks
    return host


def evm_opcode_is_host(op: int) -> bool:
    op = int(op) & 0xFF
    if _native is not None and hasattr(_native, "evm_opcode_is_host"):
        return bool(_native.evm_opcode_is_host(op))
    return op in _EVM_HOST_OPCODES


def evm_opcode_is_bridge(op: int) -> bool:
    op = int(op) & 0xFF
    if _native is not None and hasattr(_native, "evm_opcode_is_bridge"):
        return bool(_native.evm_opcode_is_bridge(op))
    return op in _EVM_BRIDGE_OPCODES


def _parse_native_segment(seg) -> dict:
    return {
        "pc": int(seg["pc"]),
        "gas_used": int(seg["gas_used"]),
        "running": bool(seg["running"]),
        "reverted": bool(seg["reverted"]),
        "return_data": bytes(seg["return_data"]),
        "stop_reason": str(seg["stop_reason"]),
        "host_opcode": seg.get("host_opcode"),
        "error": seg.get("error"),
        "steps": int(seg["steps"]),
        "stack": [int(x) for x in seg["stack"]],
        "memory": bytearray(seg["memory"]),
    }


def evm_run_pure_until_host(
    bytecode: bytes,
    pc: int,
    gas_limit: int,
    gas_used: int,
    stack: list,
    memory: bytearray,
    jumpdest_table: bytes,
    calldata: bytes,
    return_data: bytes,
    host_context: Optional[dict] = None,
    storage: Optional[dict] = None,
    host_bridge: Any = None,
) -> dict:
    if _native is not None and hasattr(_native, "evm_run_pure_until_host"):
        seg = _native.evm_run_pure_until_host(
            bytes(bytecode),
            int(pc),
            int(gas_limit),
            int(gas_used),
            stack,
            memory,
            bytes(jumpdest_table),
            bytes(calldata),
            bytes(return_data),
            host_context,
            storage,
            host_bridge,
        )
        return _parse_native_segment(seg)
    raise RuntimeError("evm_run_pure_until_host requires abs_native")


def evm_run_until_halt(
    bytecode: bytes,
    pc: int,
    gas_limit: int,
    gas_used: int,
    stack: list,
    memory: bytearray,
    jumpdest_table: bytes,
    calldata: bytes,
    return_data: bytes,
    host_context: Optional[dict] = None,
    storage: Optional[dict] = None,
    host_bridge: Any = None,
) -> dict:
    if _native is not None and hasattr(_native, "evm_run_until_halt"):
        seg = _native.evm_run_until_halt(
            bytes(bytecode),
            int(pc),
            int(gas_limit),
            int(gas_used),
            stack,
            memory,
            bytes(jumpdest_table),
            bytes(calldata),
            bytes(return_data),
            host_context,
            storage,
            host_bridge,
        )
        return _parse_native_segment(seg)
    raise RuntimeError("evm_run_until_halt requires abs_native")


def evm_memory_copy(memory: bytearray, dest: int, src: bytes, src_offset: int, size: int) -> None:
    dest = int(dest)
    src_offset = int(src_offset)
    size = int(size)
    if _native is not None and hasattr(_native, "evm_memory_copy"):
        _native.evm_memory_copy(memory, dest, src, src_offset, size)
        return
    for i in range(size):
        byte = src[src_offset + i] if (src_offset + i) < len(src) else 0
        idx = dest + i
        if idx < len(memory):
            memory[idx] = byte


def evm_keccak256_memory(memory: bytes, offset: int, size: int) -> bytes:
    if _native is not None and hasattr(_native, "evm_keccak256_memory"):
        return bytes(_native.evm_keccak256_memory(memory, int(offset), int(size)))
    end = int(offset) + int(size)
    data = memory[int(offset):end] if int(offset) < len(memory) else b""
    if len(data) < int(size):
        data = data + (b"\x00" * (int(size) - len(data)))
    return keccak256_digest(data)


def evm_deploy_address_create(deployer: str, block_number: int, init_code_len: int) -> str:
    if _native is not None and hasattr(_native, "evm_deploy_address_create"):
        return str(_native.evm_deploy_address_create(
            str(deployer),
            int(block_number),
            int(init_code_len),
        ))
    seed = f"{deployer}{int(block_number)}{int(init_code_len)}"
    return "0x" + hashlib.sha256(seed.encode()).hexdigest()[:40]


def evm_deploy_address_create2_legacy(deployer: str, salt, init_code: bytes) -> str:
    salt_text = str(int(salt)) if isinstance(salt, int) else str(salt)
    if _native is not None and hasattr(_native, "evm_deploy_address_create2_legacy"):
        return str(_native.evm_deploy_address_create2_legacy(
            str(deployer),
            salt_text,
            bytes(init_code),
        ))
    seed = f"create2:{deployer}:{salt_text}:{init_code.hex()}"
    return "0x" + hashlib.sha256(seed.encode()).hexdigest()[:40]


def evm_create2_address_eip1014(deployer: str, salt_word: int, init_code: bytes) -> str:
    salt_bytes = int(salt_word).to_bytes(32, "big")
    if _native is not None and hasattr(_native, "evm_create2_address_eip1014"):
        addr = bytes(_native.evm_create2_address_eip1014(
            str(deployer),
            salt_bytes,
            bytes(init_code),
        ))
        return "0x" + addr.hex()
    init_hash = keccak256_digest(init_code)
    prefix = b"\xff" + _address_to_bytes(deployer) + salt_bytes + init_hash
    return "0x" + keccak256_digest(prefix)[12:].hex()


def _address_to_bytes(address: str) -> bytes:
    raw = str(address or "").strip().lower().removeprefix("0x")
    if len(raw) != 40:
        raise ValueError("address must be 20-byte hex")
    return bytes.fromhex(raw)


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
    _require_native_kernel("validate_imported_block_chain")

    previous_hash = str(expected_parent_hash or "")
    previous_height = int(start_height)
    computed_hashes = block_canonical_hash_batch(blocks)
    for block, canonical_hash in zip(blocks, computed_hashes):
        height = int(block.get("height", block.get("number", 0)) or 0)
        block_hash = str(block.get("hash", block.get("block_hash", "")) or "")
        parent_hash = str(block.get("parent_hash", block.get("parent", "")) or "")
        if not block_hash or height != previous_height + 1:
            return False
        if previous_hash and parent_hash != previous_hash:
            return False
        if canonical_hash != block_hash:
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
    _require_native_kernel("sha256_hex")
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
    _require_native_kernel("merkle_root")
    return _python_merkle_root_strings(string_items)


def generate_proof(items: List[Any], target_index: int) -> List[str]:
    string_items = _string_items(items)
    if target_index < 0:
        return []
    if _native is not None:
        return _native.generate_proof(string_items, target_index)
    _require_native_kernel("generate_proof")
    return _python_generate_proof_strings(string_items, target_index)


def verify_proof(item: Any, proof: List[str], expected_root: str, target_index: int) -> bool:
    if target_index < 0:
        return False
    item_str = str(item)
    if _native is not None:
        return bool(_native.verify_proof(item_str, proof, expected_root, target_index))
    _require_native_kernel("verify_proof")
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
    _require_native_kernel("state_root_from_accounts_json")
    accounts = json.loads(accounts_json)
    return _python_state_root_from_accounts(accounts)


def state_root_from_account_blobs(blobs: List[bytes]) -> str:
    if _native is not None and hasattr(_native, "state_root_from_account_blobs"):
        return _native.state_root_from_account_blobs(list(blobs))
    _require_native_kernel("state_root_from_account_blobs")
    accounts = [json.loads(blob.decode("utf-8")) for blob in blobs]
    return _python_state_root_from_accounts(
        sorted(accounts, key=lambda row: str(row.get("address", "")))
    )


def state_root_accumulator_available() -> bool:
    return _native is not None and hasattr(_native, "StateRootAccumulator")


def new_state_root_accumulator():
    if not state_root_accumulator_available():
        _require_native_kernel("StateRootAccumulator")
    return _native.StateRootAccumulator()


def state_root_accumulator_root_from_blobs(blobs: List[bytes]) -> str:
    acc = new_state_root_accumulator()
    if blobs:
        acc.load_from_blobs(list(blobs))
    return acc.root()


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


def consensus_stake_weighted_proposer(
    validators: List[tuple[str, float, bool]],
    epoch: int,
    slot: int,
) -> Optional[str]:
    """Deterministic stake-weighted proposer (consensus_engine contract)."""
    payload = [
        (str(addr), float(stake), bool(active))
        for addr, stake, active in validators
    ]
    if _native is not None and hasattr(_native, "consensus_stake_weighted_proposer"):
        result = _native.consensus_stake_weighted_proposer(payload, int(epoch), int(slot))
        return str(result) if result else None
    total_stake = sum(stake for _, stake, active in payload if active and stake > 0)
    if total_stake <= 0:
        return None
    digest = sha256_hex(f"abs-proposer:{int(epoch)}:{int(slot)}".encode())
    ratio = int(digest[:16], 16) / float(16 ** 16)
    pick = ratio * total_stake
    current = 0.0
    for addr, stake, _active in sorted(
        ((a, s, act) for a, s, act in payload if _active and s > 0),
        key=lambda row: row[0],
    ):
        current += stake
        if current >= pick:
            return addr
    return None


def consensus_fisher_yates_committee(
    validators: List[tuple[str, float, bool]],
    slot: int,
    committee_size: int,
) -> List[str]:
    """Deterministic Fisher-Yates committee shuffle (consensus_engine contract)."""
    payload = [
        (str(addr), float(stake), bool(active))
        for addr, stake, active in validators
    ]
    if _native is not None and hasattr(_native, "consensus_fisher_yates_committee"):
        return [
            str(addr)
            for addr in _native.consensus_fisher_yates_committee(
                payload, int(slot), int(committee_size)
            )
        ]
    active_rows = sorted(
        [(addr, stake) for addr, stake, active in payload if active and stake > 0],
        key=lambda row: row[0],
    )
    if not active_rows:
        return []
    size = max(1, min(int(committee_size), len(active_rows)))
    order = [addr for addr, _ in active_rows]
    digest = sha256_hex(f"abs-committee:{int(slot)}".encode())
    for i in range(len(order) - 1, 0, -1):
        mix = int(sha256_hex(f"{digest}:{i}".encode())[:8], 16)
        j = mix % (i + 1)
        order[i], order[j] = order[j], order[i]
    return order[:size]


def validator_selection_proposer(
    seed: str,
    epoch: int,
    slot: int,
    validators: List[tuple[str, int]],
) -> Optional[str]:
    payload = [(str(addr), int(stake)) for addr, stake in validators]
    if _native is not None and hasattr(_native, "validator_selection_proposer"):
        result = _native.validator_selection_proposer(
            str(seed), int(epoch), int(slot), payload
        )
        return str(result) if result else None
    ranked = sorted(
        payload,
        key=lambda item: int(
            hash_text("|".join((str(seed), str(epoch), "proposer", str(slot), item[0]))),
            16,
        ),
    )
    return ranked[0][0] if ranked else None


def validator_selection_proposer_weighted(
    seed: str,
    epoch: int,
    slot: int,
    validators: List[tuple[str, int]],
) -> Optional[str]:
    payload = [(str(addr), int(stake)) for addr, stake in validators]
    if _native is not None and hasattr(_native, "validator_selection_proposer_weighted"):
        result = _native.validator_selection_proposer_weighted(
            str(seed), int(epoch), int(slot), payload
        )
        return str(result) if result else None
    canonical = sorted(payload, key=lambda item: item[0])
    total_stake = sum(stake for _, stake in canonical)
    if total_stake <= 0:
        return validator_selection_proposer(seed, epoch, slot, validators)
    target = int(
        hash_text("|".join((str(seed), str(epoch), "weighted-proposer", str(slot)))),
        16,
    ) % total_stake
    cumulative = 0
    for address, stake in canonical:
        cumulative += stake
        if cumulative > target:
            return address
    return canonical[0][0] if canonical else None


def validator_selection_committee(
    seed: str,
    epoch: int,
    validators: List[tuple[str, int]],
    committee_size: int,
) -> List[str]:
    payload = [(str(addr), int(stake)) for addr, stake in validators]
    if _native is not None and hasattr(_native, "validator_selection_committee"):
        return [
            str(addr)
            for addr in _native.validator_selection_committee(
                str(seed), int(epoch), payload, int(committee_size)
            )
        ]
    ranked = sorted(
        payload,
        key=lambda item: int(
            hash_text("|".join((str(seed), str(epoch), "committee", item[0]))),
            16,
        ),
    )
    take = min(int(committee_size), len(ranked))
    return [addr for addr, _ in ranked[:take]]


def validator_selection_shuffle(
    seed: str,
    epoch: int,
    validators: List[tuple[str, int]],
) -> List[tuple[str, int]]:
    payload = [(str(addr), int(stake)) for addr, stake in validators]
    if _native is not None and hasattr(_native, "validator_selection_shuffle"):
        return [
            (str(addr), int(stake))
            for addr, stake in _native.validator_selection_shuffle(
                str(seed), int(epoch), payload
            )
        ]
    ranked = sorted(
        payload,
        key=lambda item: int(
            hash_text("|".join((str(seed), str(epoch), "shuffle", item[0]))),
            16,
        ),
    )
    return ranked


def state_engine_root_from_accounts_json(accounts_json: str) -> str:
    if _native is not None and hasattr(_native, "state_engine_root_from_accounts_json"):
        return str(_native.state_engine_root_from_accounts_json(accounts_json))
    return sha256_hex(accounts_json.encode())[:32]


def amount_to_satoshi(amount_abs: str) -> int:
    if _native is not None and hasattr(_native, "amount_to_satoshi"):
        return int(_native.amount_to_satoshi(str(amount_abs)))
    from decimal import Decimal, ROUND_DOWN

    d = Decimal(str(amount_abs))
    return int((d * Decimal(1_000_000)).quantize(Decimal("1"), rounding=ROUND_DOWN))


def amount_apply_delta_satoshi(current_sat: int, delta_abs: str) -> int:
    if _native is not None and hasattr(_native, "amount_apply_delta_satoshi"):
        return int(_native.amount_apply_delta_satoshi(int(current_sat), str(delta_abs)))
    return max(0, int(current_sat) + amount_to_satoshi(delta_abs))


def amount_from_satoshi_float(satoshi: int) -> float:
    if _native is not None and hasattr(_native, "amount_from_satoshi_float"):
        return float(_native.amount_from_satoshi_float(int(satoshi)))
    return float(int(satoshi)) / 1_000_000.0


def state_engine_apply_transactions(accounts_json: str, txs_json: str) -> str:
    if _native is not None and hasattr(_native, "state_engine_apply_transactions"):
        return str(_native.state_engine_apply_transactions(accounts_json, txs_json))
    raise RuntimeError("state_engine_apply_transactions requires abs_native")


def plan_transfer_fees(
    gas: int,
    gas_price_wei: float,
    burn_rate: float,
    value: float = 0.0,
    gas_used: Optional[int] = None,
):
    if _native is not None and hasattr(_native, "plan_transfer_fees"):
        return _native.plan_transfer_fees(
            int(gas),
            float(gas_price_wei),
            float(burn_rate),
            float(value),
            int(gas_used) if gas_used is not None else None,
        )
    fee = float(gas) * float(gas_price_wei)
    if gas_used is not None:
        fee = max(fee, float(gas_used) * float(gas_price_wei))
    rate = max(0.0, min(1.0, float(burn_rate)))
    burned = fee * rate
    return fee, burned, fee - burned, float(value) + fee


def can_afford_transfer(sender_sat: int, total_cost_abs: float) -> bool:
    if _native is not None and hasattr(_native, "can_afford_transfer"):
        return bool(_native.can_afford_transfer(int(sender_sat), float(total_cost_abs)))
    return int(sender_sat) >= amount_to_satoshi(str(total_cost_abs))


def validate_p2p_status_payload(data: Any) -> Optional[dict]:
    """Normalize/validate gossip status payload; None if malformed."""
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False) if not isinstance(data, str) else data
    if _native is not None and hasattr(_native, "validate_p2p_status_payload"):
        result = _native.validate_p2p_status_payload(payload)
        return dict(result) if result is not None else None
    if not isinstance(data, dict):
        try:
            data = json.loads(payload)
        except Exception:
            return None
    if not isinstance(data, dict):
        return None
    try:
        height = int(data.get("height", 0) or 0)
    except (TypeError, ValueError):
        return None
    if height < 0 or height > 1_000_000_000_000:
        return None
    head_hash = str(data.get("head_hash") or "").strip()
    if len(head_hash) > 128:
        return None
    return {"height": height, "head_hash": head_hash}


def validate_p2p_attestation_payload(data: Any) -> bool:
    """Fail-closed shape check for attestation gossip (before sig verify)."""
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False) if not isinstance(data, str) else data
    if _native is not None and hasattr(_native, "validate_p2p_attestation_payload"):
        return bool(_native.validate_p2p_attestation_payload(payload))
    if not isinstance(data, dict):
        try:
            data = json.loads(payload)
        except Exception:
            return False
    if not isinstance(data, dict):
        return False
    validator = data.get("validator")
    target_hash = data.get("target_hash")
    signature = data.get("signature")
    public_key = data.get("public_key")
    if not isinstance(validator, str) or not validator or len(validator) > 128:
        return False
    if not isinstance(target_hash, str) or not target_hash or len(target_hash) > 128:
        return False
    if not isinstance(signature, str) or not signature or len(signature) % 2 or len(signature) > 512:
        return False
    if not isinstance(public_key, str) or not public_key or len(public_key) % 2 or len(public_key) > 130:
        return False
    try:
        int(signature, 16)
        int(public_key, 16)
    except ValueError:
        return False
    return True


def validate_p2p_block_announce(data: Any) -> Optional[dict]:
    """Fail-closed block gossip shape: height + hash (+ tx count bound)."""
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False) if not isinstance(data, str) else data
    if _native is not None and hasattr(_native, "validate_p2p_block_announce"):
        result = _native.validate_p2p_block_announce(payload)
        return dict(result) if result is not None else None
    if not isinstance(data, dict):
        try:
            data = json.loads(payload)
        except Exception:
            return None
    if not isinstance(data, dict):
        return None
    try:
        height = int(data.get("height", data.get("number", 0)) or 0)
    except (TypeError, ValueError):
        return None
    if height < 0 or height > 1_000_000_000_000:
        return None
    block_hash = str(data.get("hash") or "").strip()
    if not block_hash or len(block_hash) > 128:
        return None
    txs = data.get("transactions")
    if txs is not None and (not isinstance(txs, list) or len(txs) > 10_000):
        return None
    return {"height": height, "hash": block_hash}


def validate_p2p_state_root_request(data: Any) -> Optional[int]:
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False) if not isinstance(data, str) else data
    if _native is not None and hasattr(_native, "validate_p2p_state_root_request"):
        result = _native.validate_p2p_state_root_request(payload)
        return int(result) if result is not None else None
    if not isinstance(data, dict):
        try:
            data = json.loads(payload)
        except Exception:
            return None
    if not isinstance(data, dict):
        return None
    try:
        height = int(data.get("height", 0) or 0)
    except (TypeError, ValueError):
        return None
    if height < 0 or height > 1_000_000_000_000:
        return None
    return height


def validate_p2p_state_root_response(data: Any) -> Optional[dict]:
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False) if not isinstance(data, str) else data
    if _native is not None and hasattr(_native, "validate_p2p_state_root_response"):
        result = _native.validate_p2p_state_root_response(payload)
        return dict(result) if result is not None else None
    if not isinstance(data, dict):
        try:
            data = json.loads(payload)
        except Exception:
            return None
    if not isinstance(data, dict):
        return None
    try:
        height = int(data.get("height", 0) or 0)
    except (TypeError, ValueError):
        return None
    if height < 0 or height > 1_000_000_000_000:
        return None
    state_root = str(data.get("state_root") or "").strip()
    head_hash = str(data.get("head_hash") or "").strip()
    if len(state_root) > 128 or len(head_hash) > 128:
        return None
    return {"height": height, "state_root": state_root, "head_hash": head_hash}


def validate_p2p_handshake_payload(data: Any) -> Optional[dict]:
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False) if not isinstance(data, str) else data
    if _native is not None and hasattr(_native, "validate_p2p_handshake_payload"):
        result = _native.validate_p2p_handshake_payload(payload)
        return dict(result) if result is not None else None
    if not isinstance(data, dict):
        return None
    if data.get("accepted") is False:
        return {
            "chain_id": -1,
            "height": 0,
            "head_hash": "",
            "node_id": "",
            "p2p_port": 0,
            "accepted": False,
        }
    try:
        chain_id = int(data.get("chain_id"))
        height = int(data.get("height", 0) or 0)
        p2p_port = int(data.get("p2p_port", 0) or 0)
    except (TypeError, ValueError):
        return None
    if chain_id < 0 or height < 0 or p2p_port < 0 or p2p_port > 65535:
        return None
    head_hash = str(data.get("head_hash") or "").strip()
    node_id = str(data.get("node_id") or "").strip()
    if len(head_hash) > 128 or len(node_id) > 128:
        return None
    return {
        "chain_id": chain_id,
        "height": height,
        "head_hash": head_hash,
        "node_id": node_id,
        "p2p_port": p2p_port,
        "accepted": True,
    }


def validate_p2p_get_blocks_payload(data: Any) -> Optional[dict]:
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False) if not isinstance(data, str) else data
    if _native is not None and hasattr(_native, "validate_p2p_get_blocks_payload"):
        result = _native.validate_p2p_get_blocks_payload(payload)
        return dict(result) if result is not None else None
    if not isinstance(data, dict):
        return None
    try:
        from_height = int(data.get("from_height", 0) or 0)
        to_height = int(data.get("to_height", from_height) or from_height)
    except (TypeError, ValueError):
        return None
    if from_height < 0 or to_height < from_height or (to_height - from_height) > 10_000:
        return None
    return {"from_height": from_height, "to_height": to_height}


def validate_p2p_wire_tx(data: Any) -> bool:
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False) if not isinstance(data, str) else data
    if _native is not None and hasattr(_native, "validate_p2p_wire_tx"):
        return bool(_native.validate_p2p_wire_tx(payload))
    if not isinstance(data, dict):
        return False
    from_addr = data.get("from_addr", data.get("from", ""))
    to_addr = data.get("to_addr", data.get("to", ""))
    return bool(isinstance(from_addr, str) and isinstance(to_addr, str) and from_addr and to_addr)


def validate_p2p_mempool_batch(data: Any) -> Optional[int]:
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False) if not isinstance(data, str) else data
    if _native is not None and hasattr(_native, "validate_p2p_mempool_batch"):
        result = _native.validate_p2p_mempool_batch(payload)
        return int(result) if result is not None else None
    if not isinstance(data, dict):
        return None
    txs = data.get("transactions")
    if not isinstance(txs, list) or len(txs) > 500:
        return None
    for tx in txs:
        if not validate_p2p_wire_tx(tx):
            return None
    return len(txs)


def parse_p2p_wire_line(
    line: bytes,
    max_bytes: int = 2 * 1024 * 1024,
    allowed_types: Optional[List[str]] = None,
) -> Optional[dict]:
    """Fail-closed P2P envelope parse: size + UTF-8 + JSON object with type."""
    if _native is not None and hasattr(_native, "parse_p2p_wire_line"):
        try:
            result = _native.parse_p2p_wire_line(
                bytes(line),
                int(max_bytes),
                list(allowed_types) if allowed_types is not None else None,
            )
        except ValueError:
            raise
        except Exception:
            return None
        return dict(result) if result is not None else None
    text = bytes(line).decode("utf-8", errors="strict").strip()
    if not text:
        return None
    if len(line) > max(4096, min(int(max_bytes), 16 * 1024 * 1024)):
        raise ValueError(f"p2p_line_too_large: {len(line)} > {max_bytes} bytes")
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, UnicodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    msg_type = payload.get("type")
    if not isinstance(msg_type, str) or not msg_type or len(msg_type) > 64:
        return None
    if allowed_types is not None and allowed_types and msg_type not in allowed_types:
        return None
    return {"type": msg_type, "data": payload.get("data")}


def encode_p2p_wire_message(msg_type: str, data: Any = None) -> bytes:
    """Encode a newline-terminated P2P envelope."""
    data_json = "null" if data is None else json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    if _native is not None and hasattr(_native, "encode_p2p_wire_message"):
        return bytes(_native.encode_p2p_wire_message(str(msg_type), data_json))
    return (json.dumps({"type": str(msg_type), "data": data}, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def hash_sorted_json(obj_json: str) -> str:
    """SHA-256 of compact sorted-key JSON (Hasher.hash_object contract)."""
    if _native is not None and hasattr(_native, "hash_sorted_json"):
        return str(_native.hash_sorted_json(obj_json))
    value = json.loads(obj_json)
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256_hex(encoded.encode())


def verify_attestation_secp256k1(
    attestation: dict,
    signature_der: bytes,
    public_key_xy: bytes,
) -> bool:
    """Verify attestation signature over canonical {validator,target_hash,target_height,slot}."""
    payload = {
        "validator": attestation.get("validator"),
        "target_hash": attestation.get("target_hash"),
        "target_height": attestation.get("target_height"),
        "slot": attestation.get("slot"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if _native is not None and hasattr(_native, "verify_attestation_secp256k1"):
        return bool(
            _native.verify_attestation_secp256k1(
                encoded,
                bytes(signature_der),
                bytes(public_key_xy),
            )
        )
    digest = sha256_hex(encoded.encode())
    result = verify_secp256k1_sha256(digest.encode(), signature_der, public_key_xy)
    return bool(result)


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
