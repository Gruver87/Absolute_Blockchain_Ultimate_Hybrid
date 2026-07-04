#!/usr/bin/env python3
"""Native deploy address kernels (CREATE / CREATE2 legacy / EIP-1014)."""

import hashlib

from crypto import native


DEPLOYER = "0x" + "11" * 20
INIT_CODE = bytes.fromhex("60006000f3")
SALT = 0x42


def test_deploy_address_create_matches_python_reference():
    expected_seed = f"{DEPLOYER}100{len(INIT_CODE)}"
    expected = "0x" + hashlib.sha256(expected_seed.encode()).hexdigest()[:40]
    assert native.evm_deploy_address_create(DEPLOYER, 100, len(INIT_CODE)) == expected


def test_deploy_address_create2_legacy_matches_python_reference():
    seed = f"create2:{DEPLOYER}:{SALT}:{INIT_CODE.hex()}"
    expected = "0x" + hashlib.sha256(seed.encode()).hexdigest()[:40]
    assert native.evm_deploy_address_create2_legacy(DEPLOYER, SALT, INIT_CODE) == expected


def test_create2_eip1014_known_vector():
    deployer = "0x4e59b44847b379578588920ca78fbf26c0b4956c"
    salt = 0
    init_code = bytes.fromhex("80")
    addr = native.evm_create2_address_eip1014(deployer, salt, init_code)
    assert addr == "0x0f6304b06a29111e3ef42f14cb641492f6664e59"
