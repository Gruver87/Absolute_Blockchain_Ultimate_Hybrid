#!/usr/bin/env python3
"""Tests for MiniVM"""

import sys
from execution.vm import MiniVM

def test_vm():
    passed = 0
    failed = 0
    
    print("\nTesting MiniVM...")
    
    # Test 1: ADD
    vm = MiniVM()
    result = vm.execute([("PUSH", 10), ("PUSH", 20), ("ADD", None)])
    assert result["stack"][-1] == 30, "ADD failed"
    passed += 1
    print("✓ ADD test passed")
    
    # Test 2: Storage
    vm = MiniVM()
    result = vm.execute([("PUSH", 42), ("PUSH", 0), ("SSTORE", None), ("PUSH", 0), ("SLOAD", None)])
    assert result["stack"][-1] == 42, "Storage failed"
    passed += 1
    print("✓ Storage test passed")
    
    # Test 3: Memory
    vm = MiniVM()
    result = vm.execute([("PUSH", 0x1234), ("PUSH", 0), ("MSTORE", None), ("PUSH", 0), ("MLOAD", None)])
    assert result["stack"][-1] == 0x1234, "Memory failed"
    passed += 1
    print("✓ Memory test passed")
    
    # Test 4: Gas
    try:
        vm = MiniVM(gas_limit=10)
        vm.execute([("PUSH", 1), ("PUSH", 2), ("ADD", None), ("MUL", None)])
        assert False, "Should run out of gas"
    except Exception as e:
        if "Out of gas" in str(e):
            passed += 1
            print("✓ Gas test passed")
        else:
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0

if __name__ == "__main__":
    success = test_vm()
    sys.exit(0 if success else 1)
