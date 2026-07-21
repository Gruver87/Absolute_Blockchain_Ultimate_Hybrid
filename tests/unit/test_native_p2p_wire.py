#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rust-backed P2P wire envelope + attestation verify parity."""

import json

import pytest

from crypto import native
from crypto.validator_keys import ValidatorKeys
from crypto.wallet import Wallet
from network.p2p_node import ALLOWED_WIRE_TYPES, DEFAULT_MAX_P2P_LINE_BYTES


def test_parse_p2p_wire_line_accepts_valid_envelope():
    line = b'{"type":"ping","data":null}\n'
    msg = native.parse_p2p_wire_line(line, DEFAULT_MAX_P2P_LINE_BYTES, list(ALLOWED_WIRE_TYPES))
    assert msg == {"type": "ping", "data": None}


def test_parse_p2p_wire_line_rejects_unknown_type():
    line = b'{"type":"evil","data":{}}\n'
    assert native.parse_p2p_wire_line(line, DEFAULT_MAX_P2P_LINE_BYTES, list(ALLOWED_WIRE_TYPES)) is None


def test_parse_p2p_wire_line_rejects_oversized():
    huge = b'{"type":"ping","data":"' + (b"a" * (DEFAULT_MAX_P2P_LINE_BYTES + 10)) + b'"}'
    with pytest.raises(ValueError, match="p2p_line_too_large"):
        native.parse_p2p_wire_line(huge, DEFAULT_MAX_P2P_LINE_BYTES, list(ALLOWED_WIRE_TYPES))


def test_encode_p2p_wire_message_roundtrip():
    raw = native.encode_p2p_wire_message("status", {"height": 42, "peers": 2})
    assert raw.endswith(b"\n")
    msg = native.parse_p2p_wire_line(raw, DEFAULT_MAX_P2P_LINE_BYTES, list(ALLOWED_WIRE_TYPES))
    assert msg["type"] == "status"
    assert msg["data"]["height"] == 42


def test_hash_sorted_json_matches_python_compact():
    payload = {"b": 2, "a": [1, {"z": 9, "y": 8}]}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    assert native.hash_sorted_json(encoded) == native.sha256_hex(encoded.encode())


def test_verify_attestation_secp256k1_roundtrip():
    wallet = Wallet.create_new()
    keys = ValidatorKeys().initialize(wallet)
    att = keys.sign_attestation({"hash": "ab" * 32, "number": 7}, slot=3)
    assert keys.verify_attestation(att) is True
    att["signature"] = "00" * 64
    assert keys.verify_attestation(att) is False


def test_native_parse_p2p_wire_rejects_non_object():
    if not native.native_available():
        return
    assert native.parse_p2p_wire_line(b"[1,2,3]\n", 65536, None) is None


def test_validate_p2p_status_payload_ok_and_reject():
    ok = native.validate_p2p_status_payload({"height": 12, "head_hash": "ab" * 32})
    assert ok == {"height": 12, "head_hash": "ab" * 32}
    assert native.validate_p2p_status_payload({"height": -1}) is None
    assert native.validate_p2p_status_payload({"height": 1, "head_hash": "x" * 200}) is None
    assert native.validate_p2p_status_payload([1, 2, 3]) is None


def test_validate_p2p_attestation_payload_shape():
    good = {
        "validator": "0x" + "a" * 40,
        "target_hash": "ab" * 32,
        "target_height": 7,
        "slot": 3,
        "signature": "ab" * 32,
        "public_key": "cd" * 64,
    }
    assert native.validate_p2p_attestation_payload(good) is True
    bad = dict(good)
    bad["signature"] = "zz"
    assert native.validate_p2p_attestation_payload(bad) is False
    missing = dict(good)
    missing.pop("public_key")
    assert native.validate_p2p_attestation_payload(missing) is False


def test_validate_p2p_block_announce_and_state_root():
    ok = native.validate_p2p_block_announce(
        {"height": 9, "hash": "ab" * 32, "transactions": []}
    )
    assert ok == {"height": 9, "hash": "ab" * 32}
    assert native.validate_p2p_block_announce({"height": 1}) is None
    assert native.validate_p2p_block_announce(
        {"height": 1, "hash": "ab" * 32, "transactions": [{}] * 10_001}
    ) is None

    assert native.validate_p2p_state_root_request({"height": 5}) == 5
    assert native.validate_p2p_state_root_request({"height": -1}) is None

    resp = native.validate_p2p_state_root_response(
        {"height": 5, "state_root": "cd" * 32, "head_hash": "ef" * 32}
    )
    assert resp["height"] == 5
    assert resp["state_root"] == "cd" * 32
    assert native.validate_p2p_state_root_response({"height": 1, "state_root": "x" * 200}) is None


def test_validate_handshake_get_blocks_wire_tx_mempool():
    hs = native.validate_p2p_handshake_payload(
        {
            "chain_id": 1,
            "height": 10,
            "head_hash": "ab" * 32,
            "node_id": "abs-18080",
            "p2p_port": 18080,
            "version": "1.0",
        }
    )
    assert hs["accepted"] is True
    assert hs["chain_id"] == 1
    assert native.validate_p2p_handshake_payload({"accepted": False, "reason": "max_peers"})[
        "accepted"
    ] is False
    assert native.validate_p2p_handshake_payload({"height": 1}) is None

    rng = native.validate_p2p_get_blocks_payload({"from_height": 1, "to_height": 5})
    assert rng == {"from_height": 1, "to_height": 5}
    assert native.validate_p2p_get_blocks_payload({"from_height": 5, "to_height": 1}) is None
    assert native.validate_p2p_get_blocks_payload(
        {"from_height": 0, "to_height": 20_000}
    ) is None

    tx = {
        "from": "0x" + "a" * 40,
        "to": "0x" + "b" * 40,
        "value": 1.0,
        "nonce": 0,
        "gas": 21000,
    }
    assert native.validate_p2p_wire_tx(tx) is True
    assert native.validate_p2p_wire_tx({"from": "", "to": "x"}) is False
    assert native.validate_p2p_mempool_batch({"transactions": [tx]}) == 1
    assert native.validate_p2p_mempool_batch({"transactions": [tx] * 501}) is None
