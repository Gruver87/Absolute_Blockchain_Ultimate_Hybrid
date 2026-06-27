# -*- coding: utf-8 -*-
# test_v48.py - JSON-RPC Tests (NO EMOJIS)
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def log(msg):
    sys.stdout.write(msg + "\n")

log("=" * 70)
log("v48 - JSON-RPC API")
log("eth_* METHODS + META MASK COMPATIBILITY")
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
log("\n[TEST 1] RPC Server initialization")
from rpc.server import JSONRPCServer

class MockStorage:
    def get_latest_block_number(self): return 5
    def get_metadata(self, key): return "1337"
    def get_balance(self, addr): return 1000000000000000000
    def get_latest_block(self):
        return {"number": 5, "hash": "0xabc", "parent_hash": "0xdef", "timestamp": 12345, "proposer": "0xprop", "state_root": "0xstate", "tx_root": "0xtx", "transactions": []}
    def get_block_by_number(self, num): return {"number": num}
    def get_block(self, h): return {"number": 5}

class MockPeerManager:
    def get_peer_count(self): return 3

class MockNode:
    def __init__(self):
        self.storage = MockStorage()
        self.peer_manager = MockPeerManager()

server = JSONRPCServer(MockNode(), host="127.0.0.1", port=18545)
test("RPC server created", server is not None)

# =========================================================
log("\n[TEST 2] eth_blockNumber")
result = server.eth_blockNumber([])
test("eth_blockNumber returns hex", result.startswith("0x"))
test("eth_blockNumber correct", result == "0x5")

# =========================================================
log("\n[TEST 3] eth_chainId")
result = server.eth_chainId([])
test("eth_chainId returns hex", result.startswith("0x"))

# =========================================================
log("\n[TEST 4] eth_getBalance")
result = server.eth_getBalance(["0x123"])
test("eth_getBalance returns hex", result.startswith("0x"))

# =========================================================
log("\n[TEST 5] eth_getBlockByNumber")
result = server.eth_getBlockByNumber(["latest", False])
test("eth_getBlockByNumber returns dict", isinstance(result, dict) or result is None)

# =========================================================
log("\n[TEST 6] net_version")
result = server.net_version([])
test("net_version returns string", isinstance(result, str))

# =========================================================
log("\n[TEST 7] web3_clientVersion")
result = server.web3_clientVersion([])
test("web3_clientVersion returns string", isinstance(result, str))

# =========================================================
log("\n[TEST 8] Unknown method error")
response = server.handle_request({"jsonrpc": "2.0", "method": "unknown_method", "params": [], "id": 1})
test("Unknown method returns error", "error" in response)

# =========================================================
log("\n" + "=" * 70)
log(f"RESULTS: {passed}/{total} tests passed")
if passed == total:
    log("[SUCCESS] ALL TESTS PASSED!")
log("=" * 70)
import sys
if __name__ == '__main__':
    raise SystemExit(0 if passed == total else 1)
