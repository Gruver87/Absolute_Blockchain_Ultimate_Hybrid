import hashlib

from crypto import native
from crypto.merkle import (
    generate_proof,
    hash_data,
    merkle_root,
    merkle_root_from_proof,
    verify_proof,
)


def test_sha256_facade_matches_hashlib():
    payload = b"absolute-native-crypto"
    assert native.sha256_hex(payload) == hashlib.sha256(payload).hexdigest()
    assert native.double_sha256_hex(payload) == hashlib.sha256(
        hashlib.sha256(payload).digest()
    ).hexdigest()


def test_native_crypto_status_self_test():
    status = native.native_crypto_status(required=native.native_available())
    assert "sha256" in status["kernels"]
    assert "secp256k1_verify" in status["kernels"]
    if native.native_available():
        assert status["self_test"] is True


def test_merkle_root_matches_python_kernel_for_consensus_cases():
    cases = [
        [],
        ["empty"],
        ["tx1"],
        ["tx1", "tx2"],
        ["tx1", "tx2", "tx3"],
        ["tx1", "tx2", "tx3", "tx4", "tx5"],
        [{"from": "0xaaa", "to": "0xbbb", "value": 7}],
    ]

    for items in cases:
        expected = native._python_merkle_root_strings([str(item) for item in items])
        assert merkle_root(items) == expected


def test_merkle_proof_roundtrip_matches_python_kernel():
    items = ["tx1", "tx2", "tx3", "tx4", "tx5"]
    target_index = 2

    root = merkle_root(items)
    proof = generate_proof(items, target_index)

    assert proof == native._python_generate_proof_strings(items, target_index)
    assert verify_proof(items[target_index], proof, root, target_index)
    assert merkle_root_from_proof(items[target_index], proof, target_index) == root
    assert not verify_proof("tampered", proof, root, target_index)


def test_hash_data_preserves_historical_str_encoding():
    data = {"b": 2, "a": 1}
    assert hash_data(data) == hashlib.sha256(str(data).encode()).hexdigest()


def test_installed_abs_native_matches_python_kernel_when_available():
    if not native.native_available():
        return

    import abs_native

    items = ["tx1", "tx2", "tx3", "tx4", "tx5"]
    proof = abs_native.generate_proof(items, 4)
    root = native._python_merkle_root_strings(items)

    assert abs_native.merkle_root(items) == root
    assert abs_native.verify_proof(items[4], proof, root, 4)
    assert abs_native.merkle_root_from_proof(items[4], proof, 4) == root
