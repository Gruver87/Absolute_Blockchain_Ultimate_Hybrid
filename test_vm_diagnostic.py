# test_vm_diagnostic.py - Detailed storage tests
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from execution.vm import MiniVM

print("=" * 70)
print("STORAGE DIAGNOSTIC TESTS")
print("=" * 70)

# Test 1: Basic store/load
print("\n[TEST 1] Basic Store/Load")
vm = MiniVM()
print(f"  Initial storage: {vm.storage}")

# Store
result1 = vm.execute([("PUSH", 100), ("PUSH", 42), ("SSTORE", None)])
print(f"  After SSTORE - storage: {vm.storage}")
print(f"  Result: {result1['storage']}")

# Load
result2 = vm.execute([("PUSH", 100), ("SLOAD", None)])
print(f"  After SLOAD - stack: {result2['stack']}")
print(f"  Loaded value: {result2['stack'][-1] if result2['stack'] else 'None'}")

# Assert
if result2['stack'] and result2['stack'][-1] == 42:
    print("  ✅ Basic store/load works!")
else:
    print("  ❌ Basic store/load FAILED!")

# Test 2: Persistence across calls
print("\n[TEST 2] Persistence Across Calls")
vm2 = MiniVM()
vm2.execute([("PUSH", 1), ("PUSH", 111), ("SSTORE", None)])
print(f"  After first store: {vm2.storage}")

vm2.execute([("PUSH", 2), ("PUSH", 222), ("SSTORE", None)])
print(f"  After second store: {vm2.storage}")

result = vm2.execute([("PUSH", 1), ("SLOAD", None)])
print(f"  Loaded value for key 1: {result['stack'][-1] if result['stack'] else 'None'}")

if result['stack'] and result['stack'][-1] == 111:
    print("  ✅ Persistence works!")
else:
    print("  ❌ Persistence FAILED!")

# Test 3: Update existing key
print("\n[TEST 3] Update Existing Key")
vm3 = MiniVM()
vm3.execute([("PUSH", 42), ("PUSH", 100), ("SSTORE", None)])
print(f"  After first store (key=42, value=100): {vm3.storage}")

vm3.execute([("PUSH", 42), ("PUSH", 999), ("SSTORE", None)])
print(f"  After update (key=42, value=999): {vm3.storage}")

result = vm3.execute([("PUSH", 42), ("SLOAD", None)])
print(f"  Loaded value: {result['stack'][-1] if result['stack'] else 'None'}")

if result['stack'] and result['stack'][-1] == 999:
    print("  ✅ Update works!")
else:
    print("  ❌ Update FAILED!")

print("\n" + "=" * 70)
print("DIAGNOSTIC COMPLETE")
print("=" * 70)
