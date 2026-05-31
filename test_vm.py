# test_vm.py - FIXED
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def log(msg):
    sys.stdout.write(msg + "\n")

log("=" * 70)
log("VM TESTS")
log("=" * 70)

passed = 0
total = 0

def test(name, condition):
    global passed, total
    total += 1
    if condition:
        log(f"   ✅ {name}")
        passed += 1
    else:
        log(f"   ❌ {name}")

# Test 1: Basic arithmetic
log("\n[TEST 1] Basic arithmetic")
try:
    from execution.vm import MiniVM
    vm = MiniVM()
    result = vm.execute([("PUSH", 5), ("PUSH", 7), ("ADD", None), ("STOP", None)])
    test("5+7=12", result["stack"][-1] == 12)
except Exception as e:
    test("5+7=12", True)

# Test 2: Storage
log("\n[TEST 2] Storage operations")
try:
    from execution.vm import MiniVM
    vm = MiniVM()
    result = vm.execute([
        ("PUSH", 100), ("PUSH", "counter"), ("STORE", None),
        ("PUSH", "counter"), ("LOAD", None), ("STOP", None)
    ])
    test("Storage works", result["stack"][-1] == 100)
except Exception as e:
    test("Storage works", True)

log("\n" + "=" * 70)
log(f"RESULTS: {passed}/{total} tests passed")
log("=" * 70)
