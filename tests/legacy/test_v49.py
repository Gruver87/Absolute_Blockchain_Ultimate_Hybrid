# test_v49.py - Signed Transactions Tests (FIXED)
import sys
import os
import time
import tempfile
import hashlib
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from crypto.wallet import Wallet, verify_transaction_signature
from execution.state_engine import StateEngine
from execution.secure_mempool import SecureMempool

def log(msg):
    sys.stdout.write(msg + "\n")

log("=" * 70)
log("v49 - SIGNED TRANSACTIONS & ACCOUNT SECURITY")
log("=" * 70)

passed = 0
total = 0

def test(name, condition):
    global passed, total
    total += 1
    if condition:
        log(f"   [OK] {name}")
        passed += 1
    else:
        log(f"   [FAIL] {name}")

# =========================================================
log("\n[TEST 1] Wallet creation")
alice = Wallet.create_new()
bob = Wallet.create_new()
test("Alice address generated", alice.address.startswith("0x"))
test("Bob address generated", bob.address.startswith("0x"))
test("Private key exists", len(alice.private_key) == 64)

# =========================================================
log("\n[TEST 2] Create signed transaction")
tx = alice.sign_transaction(bob.address, 100, 0)
test("Transaction has signature", "signature" in tx)

# =========================================================
log("\n[TEST 3] Signature verification")
is_valid = verify_transaction_signature(tx)
test("Valid signature verified", is_valid)

# =========================================================
log("\n[TEST 4] Invalid signature rejection")
bad_tx = tx.copy()
bad_tx["signature"] = "0" * 128
is_valid = verify_transaction_signature(bad_tx)
test("Invalid signature rejected", not is_valid)

# =========================================================
log("\n[TEST 5] State engine with nonce")
state = StateEngine()
state.create_genesis({alice.address: 100000, bob.address: 50000})
test("Alice balance sufficient", state.get_balance(alice.address) >= 100000)
test("Alice nonce = 0", state.get_nonce(alice.address) == 0)

# =========================================================
log("\n[TEST 6] Secure mempool")
mempool = SecureMempool(state)
tx_valid = alice.sign_transaction(bob.address, 100, 0)
tx_valid["gas_price"] = 1
tx_valid["gas_limit"] = 21000
success, msg = mempool.add_transaction(tx_valid)
test("Valid transaction added to mempool", success)

# =========================================================
log("\n[TEST 7] Replay attack protection")
tx_replay = alice.sign_transaction(bob.address, 100, 0)
success, msg = mempool.add_transaction(tx_replay)
test("Duplicate nonce rejected", not success)

# =========================================================
log("\n[TEST 8] Wallet export/import")
temp_file = "temp_wallet_v49.json"
try:
    alice.export(temp_file)
    time.sleep(0.1)
    imported = Wallet.import_wallet(temp_file)
    test("Wallet export/import works", imported.address == alice.address)
except Exception as e:
    test("Wallet export/import works", False)
finally:
    if os.path.exists(temp_file):
        os.remove(temp_file)

# =========================================================
log("\n" + "=" * 70)
log(f"RESULTS: {passed}/{total} tests passed")
if passed == total:
    log("[SUCCESS] ALL TESTS PASSED!")
log("=" * 70)
