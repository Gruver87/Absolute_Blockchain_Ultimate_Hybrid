# test_vm.py - TESTS WITH CORRECT SEMANTICS
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from execution.vm import MiniVM

passed = 0
total = 0

def test(name, condition):
    global passed, total
    total += 1
    status = "?" if condition else "?"
    print(f"   {status} {name}")
    if condition:
        passed += 1

print("=" * 70)
print("MINI-EVM - CORRECT SEMANTICS TESTS")
print("=" * 70)
print("\nSemantics: PUSH key, PUSH value, SSTORE")
print("           PUSH key, SLOAD")
print("=" * 70)

# Test 1: Store using correct semantics
print("\n[1] SSTORE (correct order)")
vm = MiniVM()
# CORRECT: PUSH key, PUSH value, SSTORE
result = vm.execute([
    ("PUSH", 100),   # key
    ("PUSH", 42),    # value
    ("SSTORE", None)
])
test("Store value with correct semantics", result["success"])

# Test 2: Load
print("\n[2] SLOAD")
result = vm.execute([
    ("PUSH", 100),   # key to load
    ("SLOAD", None)
])
test("Load stored value", result["stack"] and result["stack"][-1] == 42)

# Test 3: Persistence
print("\n[3] Persistence across calls")
vm2 = MiniVM()
vm2.execute([("PUSH", 1), ("PUSH", 111), ("SSTORE", None)])
vm2.execute([("PUSH", 2), ("PUSH", 222), ("SSTORE", None)])
result = vm2.execute([("PUSH", 1), ("SLOAD", None)])
test("Storage persists", result["stack"] and result["stack"][-1] == 111)

# Test 4: Update
print("\n[4] Update existing key")
vm3 = MiniVM()
vm3.execute([("PUSH", 42), ("PUSH", 100), ("SSTORE", None)])
vm3.execute([("PUSH", 42), ("PUSH", 999), ("SSTORE", None)])
result = vm3.execute([("PUSH", 42), ("SLOAD", None)])
test("Update works", result["stack"] and result["stack"][-1] == 999)

# Test 5: Non-existent key
print("\n[5] Non-existent key")
vm4 = MiniVM()
result = vm4.execute([("PUSH", 999), ("SLOAD", None)])
test("Missing key returns 0", result["stack"] and result["stack"][-1] == 0)

print("\n" + "=" * 70)
print(f"RESULTS: {passed}/{total} tests passed")

if passed == total:
    print("\n?? ALL TESTS PASSED! VM is fully functional!")
    print("\n? Semantic decision: PUSH key, PUSH value, SSTORE")
    sys.exit(0)
else:
    print(f"\n?? Failed: {total - passed} tests")
    sys.exit(1)
