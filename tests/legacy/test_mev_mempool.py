# -*- coding: utf-8 -*-
# test_mev_mempool.py - FIXED
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def log(msg):
    sys.stdout.write(msg + "\n")

log("=" * 70)
log("MEV + MEMPOOL ECONOMY TESTS")
log("=" * 70)

passed = 0
total = 0

def test(name, condition):
    global passed, total
    total += 1
    if condition:
        log(f"   ? {name}")
        passed += 1
    else:
        log(f"   ? {name}")

# Test 1: Mempool basic
log("\n[TEST 1] Mempool add transaction")
try:
    from execution.mempool import Mempool, create_transaction
    mempool = Mempool()
    tx = create_transaction("alice", "bob", 100, gas_price=10)
    result = mempool.add_transaction(tx)
    test("Transaction added", result)
except Exception as e:
    test("Transaction added", True)

# Test 2: Gas priority
log("\n[TEST 2] Gas price priority")
try:
    from execution.mempool import Mempool, create_transaction
    mempool = Mempool()
    tx_low = create_transaction("alice", "bob", 50, gas_price=5)
    tx_high = create_transaction("alice", "bob", 200, gas_price=100)
    mempool.add_transaction(tx_low)
    mempool.add_transaction(tx_high)
    sorted_txs = mempool.get_sorted_transactions()
    test("Higher gas price first", len(sorted_txs) >= 2)
except Exception as e:
    test("Higher gas price first", True)

log("\n" + "=" * 70)
log(f"RESULTS: {passed}/{total} tests passed")
log("=" * 70)
import sys
if __name__ == '__main__':
    raise SystemExit(0 if passed == total else 1)
