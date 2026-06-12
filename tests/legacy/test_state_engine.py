# -*- coding: utf-8 -*-
# test_state_engine.py - State Engine Tests (FIXED)
import sys
import os
import hashlib
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from execution.state_engine import StateEngine

def log(msg):
    sys.stdout.write(msg + "\n")

log("=" * 70)
log("STATE ENGINE - MINI EXECUTION LAYER")
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
log("\n[TEST 1] Genesis creation")
engine = StateEngine()
genesis = engine.create_genesis({"alice": 1000, "bob": 500})
test("Genesis created", engine.state is not None)
test("Alice balance = 1000", engine.get_balance("alice") == 1000)
test("Bob balance = 500", engine.get_balance("bob") == 500)

# =========================================================
log("\n[TEST 2] Transfer transaction")
block = {
    "number": 1,
    "parent_hash": "0x0",
    "timestamp": 12345,
    "hash": "0x123",
    "transactions": [
        {"from": "alice", "to": "bob", "value": 100, "nonce": 0}
    ]
}
new_state = engine.transition(block)
test("State transition returns new state", new_state is not None)
test("Alice balance decreased", engine.get_balance("alice") == 900)
test("Bob balance increased", engine.get_balance("bob") == 600)

# =========================================================
log("\n[TEST 3] Nonce tracking")
test("Alice nonce = 1", engine.get_nonce("alice") == 1)

# =========================================================
log("\n[TEST 4] State root")
root = engine.get_state_root()
test("State root exists", len(root) == 32)
test("State root is hex string", all(c in "0123456789abcdef" for c in root))

# =========================================================
log("\n[TEST 5] Multiple transactions")
block2 = {
    "number": 2,
    "parent_hash": "0x123",
    "timestamp": 12346,
    "hash": "0x124",
    "transactions": [
        {"from": "alice", "to": "bob", "value": 50, "nonce": 1},
        {"from": "bob", "to": "alice", "value": 30, "nonce": 0}
    ]
}
engine.transition(block2)
test("Multiple txs: Alice balance", engine.get_balance("alice") == 880)
test("Multiple txs: Bob balance", engine.get_balance("bob") == 620)

# =========================================================
log("\n[TEST 6] Copy state")
engine2 = engine.copy()
test("Copy created", engine2 is not None)
test("Copy has same balance", engine2.get_balance("alice") == engine.get_balance("alice"))

# =========================================================
log("\n[TEST 7] Insufficient balance rejection")
engine3 = StateEngine()
engine3.create_genesis({"alice": 10, "bob": 0})
try:
    block_bad = {
        "number": 1,
        "parent_hash": "0x0",
        "timestamp": 12345,
        "hash": "0xbad",
        "transactions": [
            {"from": "alice", "to": "bob", "value": 100, "nonce": 0}
        ]
    }
    engine3.transition(block_bad)
    test("Insufficient balance detected", False)
except Exception as e:
    test("Insufficient balance detected", "balance" in str(e).lower() or "insufficient" in str(e).lower())

# =========================================================
log("\n" + "=" * 70)
log(f"RESULTS: {passed}/{total} tests passed")
if passed == total:
    log("[SUCCESS] ALL TESTS PASSED!")
log("=" * 70)
import sys
if __name__ == '__main__':
    raise SystemExit(0 if passed == total else 1)
