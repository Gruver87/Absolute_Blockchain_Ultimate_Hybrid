# test_v50.py - Block Sync Tests (FIXED)
import sys
import os
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def log(msg):
    sys.stdout.write(msg + "\n")

log("=" * 70)
log("v50 - BLOCK SYNC & PEER STATE SYNC")
log("Testing sync manager components")
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
log("\n[TEST 1] Message types exist")

from network.p2p.messages import MessageType
has_block_announce = hasattr(MessageType, 'BLOCK_ANNOUNCE')
has_block_request = hasattr(MessageType, 'BLOCK_REQUEST')
has_block_response = hasattr(MessageType, 'BLOCK_RESPONSE')
has_sync_request = hasattr(MessageType, 'SYNC_REQUEST')
has_sync_response = hasattr(MessageType, 'SYNC_RESPONSE')

test("BLOCK_ANNOUNCE exists", has_block_announce)
test("BLOCK_REQUEST exists", has_block_request)
test("BLOCK_RESPONSE exists", has_block_response)
test("SYNC_REQUEST exists", has_sync_request)
test("SYNC_RESPONSE exists", has_sync_response)

# =========================================================
log("\n[TEST 2] Sync Manager imports")
try:
    from network.sync.sync_manager import SyncManager
    test("SyncManager imports", True)
except ImportError as e:
    test("SyncManager imports", False)
    log(f"   Error: {e}")

# =========================================================
log("\n[TEST 3] Helper functions")
from network.p2p.messages import (
    create_block_announce,
    create_block_request,
    create_block_response,
    create_sync_request,
    create_sync_response
)

announce = create_block_announce("0x123", 100)
test("create_block_announce works", announce["type"] == "block_announce")

request = create_block_request("0x123")
test("create_block_request works", request["type"] == "block_request")

# =========================================================
log("\n[TEST 4] Mock node with sync manager")

# Правильный мок-объект с методами (не лямбдами)
class MockStorage:
    def get_latest_block_number(self):
        return 50
    
    def get_block(self, hash_val):
        return None
    
    def get_block_by_number(self, num):
        return {"number": num, "hash": f"0x{num}"}

class MockPeer:
    def __init__(self, pid):
        self.id = pid

class MockPeerManager:
    def get_peer(self, pid):
        return MockPeer(pid)

class MockP2PServer:
    def send_message(self, peer, msg):
        pass
    def broadcast(self, msg):
        pass

class MockImporter:
    def import_block(self, block):
        return True

class MockNode:
    def __init__(self):
        self.storage = MockStorage()
        self.peer_manager = MockPeerManager()
        self.p2p_server = MockP2PServer()
        self.block_importer = MockImporter()

mock_node = MockNode()
sync_mgr = SyncManager(mock_node)
test("SyncManager created", sync_mgr is not None)

# =========================================================
log("\n[TEST 5] Peer tracking")
sync_mgr.update_peer_state("peer1", 100, "0xabc")
test("Peer state updated", sync_mgr.get_peer_height("peer1") == 100)

best = sync_mgr.get_best_peer()
test("Best peer found", best == "peer1")

# =========================================================
log("\n[TEST 6] Needs sync detection")
# Add peer2 with higher height
sync_mgr.update_peer_state("peer2", 200, "0xdef")
needs_sync = sync_mgr.needs_sync()
test("Needs sync returns bool", isinstance(needs_sync, bool))
test("Needs sync true when peer ahead", needs_sync == True)

# =========================================================
log("\n[TEST 7] Block announcement handling")
try:
    sync_mgr.handle_block_announce("peer1", "0xnewblock", 150)
    test("Block announce handled", True)
except Exception as e:
    test("Block announce handled", False)
    log(f"   Error: {e}")

# =========================================================
log("\n[TEST 8] Sync manager stats")
stats = sync_mgr.get_stats()
test("Stats has tracked_peers", "tracked_peers" in stats)
test("Stats has best_peer", "best_peer" in stats)
test("Stats has needs_sync", "needs_sync" in stats)

# =========================================================
log("\n[TEST 9] Get local height")
local_height = sync_mgr._get_local_height()
test("Get local height returns number", isinstance(local_height, int))
test("Local height = 50", local_height == 50)

# =========================================================
log("\n[TEST 10] Get blocks from height")
blocks = sync_mgr._get_blocks_from_height(51, limit=5)
test("Get blocks returns list", isinstance(blocks, list))

# =========================================================
log("\n" + "=" * 70)
log(f"RESULTS: {passed}/{total} tests passed")

if passed == total:
    log("[SUCCESS] v50 BLOCK SYNC READY!")
    log("")
    log("What v50 adds:")
    log("  -> Block propagation (BLOCK_ANNOUNCE/REQUEST/RESPONSE)")
    log("  -> Chain sync (SYNC_REQUEST/RESPONSE)")
    log("  -> Peer height tracking")
    log("  -> Automatic sync with best peer")
    log("  -> Fork detection hook")
    log("")
    log("Next: integrate sync_manager into node and test multi-node!")
else:
    log(f"[WARN] Failed: {total - passed}")
log("=" * 70)
