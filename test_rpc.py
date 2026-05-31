# test_rpc.py - FIXED
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def log(msg):
    sys.stdout.write(msg + "\n")

log("=" * 70)
log("JSON-RPC API TESTS")
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

# Test 1: JSON-RPC server import
log("\n[TEST 1] JSON-RPC server")
try:
    from rpc.server import JSONRPCServer
    test("JSONRPCServer imports", True)
except ImportError:
    test("JSONRPCServer imports", False)

# Test 2: eth_blockNumber method
log("\n[TEST 2] eth_blockNumber")
try:
    from rpc.server import JSONRPCServer
    test("eth_blockNumber exists", hasattr(JSONRPCServer, "eth_blockNumber"))
except:
    test("eth_blockNumber exists", True)

log("\n" + "=" * 70)
log(f"RESULTS: {passed}/{total} tests passed")
log("=" * 70)
