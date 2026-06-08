# test_sync_engine_v2.py
import sys
import os
import builtins

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Восстанавливаем print если был переопределён
if not callable(print):
    print = builtins.print

from sync.sync_engine import SyncEngine

print("=" * 70)
print("SYNC ENGINE — FAST CATCH-UP")
print("Peer head selection, chain download, state sync")
print("=" * 70)

passed = 0
total = 0

def test(name, condition):
    global passed, total
    total += 1
    if condition:
        print(f"   ✅ {name}")
        passed += 1
    else:
        print(f"   ❌ {name}")

# =========================================================
print("\n[SETUP] Creating mock node and peers")

class MockConsensus:
    def __init__(self):
        self.weights = {}
        self.head = None

    def get_cumulative_weight(self, block_hash):
        return self.weights.get(block_hash, 0)

    def set_head(self, head):
        self.head = head

    def add_block(self, block):
        pass

class MockNode:
    def __init__(self):
        self.consensus = MockConsensus()
        self.blocks = {}

    def get_block(self, block_hash):
        return self.blocks.get(block_hash)

    def add_block(self, block):
        self.blocks[block["hash"]] = block

# Создаём пиров
class MockPeer:
    def __init__(self, head_hash, head_weight):
        self.head = {"hash": head_hash}
        self.weight = head_weight

peers = [
    MockPeer("0xhead_heavy", 1000),
    MockPeer("0xhead_light", 100),
]

node = MockNode()

# Добавляем блоки
node.add_block({"hash": "0xgenesis", "number": 0, "parent": None})
node.add_block({"hash": "0xblock1", "number": 1, "parent": "0xgenesis"})
node.add_block({"hash": "0xhead_heavy", "number": 2, "parent": "0xblock1"})
node.add_block({"hash": "0xhead_light", "number": 2, "parent": "0xblock1"})

node.consensus.weights = {
    "0xhead_heavy": 1000,
    "0xhead_light": 100
}

# =========================================================
print("\n[TEST 1] Sync engine creation")
sync = SyncEngine(node)

sync.add_peer(peers[0])
sync.add_peer(peers[1])

test("Peers added", len(sync.get_peers()) == 2)

# =========================================================
print("\n[TEST 2] Request heads")
heads = sync.request_heads()
test("Heads requested", len(heads) == 2)

# =========================================================
print("\n[TEST 3] Select best head (by weight)")
best_head = sync.select_best_head(heads)
test("Best head selected", best_head == "0xhead_heavy")

# =========================================================
print("\n[TEST 4] Chain download")
chain = sync.download_chain("0xhead_heavy")
test("Chain downloaded", len(chain) > 0)
test("Chain includes genesis", chain[0].get("hash") == "0xgenesis")
test("Chain includes head", chain[-1].get("hash") == "0xhead_heavy")

# =========================================================
print("\n[TEST 5] Fast sync")
result = sync.fast_sync()
test("Fast sync started", result == True)
test("Sync flag cleared after finish", sync.is_syncing == False)

# =========================================================
print("\n[TEST 6] Sync status")
status = sync.get_status()
test("Status contains syncing", "syncing" in status)
test("Status contains peers", "peers" in status)
test("Status contains progress", "progress" in status)

# =========================================================
print("\n[TEST 7] Reset")
sync.reset()
test("Reset cleared sync flag", sync.is_syncing == False)
test("Reset cleared progress", sync.sync_progress == 0)

print("\n" + "=" * 70)
print(f"📊 RESULTS: {passed}/{total} tests passed")
if passed == total:
    print("🎉 SYNC ENGINE — ALL TESTS PASSED!")
    print("")
    print("   ✅ Peer management")
    print("   ✅ Head request from peers")
    print("   ✅ Best head selection (weight-based)")
    print("   ✅ Chain download (parent walk)")
    print("   ✅ Fast sync procedure")
    print("   ✅ Sync status tracking")
    print("")
    print("🏆 Sync engine ready! Node can now catch up with network")
else:
    print(f"⚠️ Failed: {total - passed}")
print("=" * 70)
