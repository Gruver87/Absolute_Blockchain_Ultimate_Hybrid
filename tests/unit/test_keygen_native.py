#!/usr/bin/env python3
"""Key derivation uses native kernels; Ethereum helper available."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from crypto import native
from crypto.keys import KeyGenerator


def test_derive_address_stable_sha256_tail():
    pubkey = bytes.fromhex("01" * 32 + "02" * 32)
    addr1 = KeyGenerator.derive_address(pubkey)
    addr2 = KeyGenerator.derive_address(pubkey)
    assert addr1 == addr2
    assert addr1.startswith("0x")
    assert len(addr1) == 42
    expected = "0x" + native.sha256_hex(pubkey)[-40:]
    assert addr1 == expected


@pytest.mark.skipif(not native.native_available(), reason="abs_native required")
def test_derive_address_eth_matches_rust():
    keypair = KeyGenerator.generate_keypair()
    eth = KeyGenerator.derive_address_eth(keypair.public_key)
    assert eth == native.pubkey_to_eth_address(keypair.public_key)
    assert eth.startswith("0x")
    assert len(eth) == 42
