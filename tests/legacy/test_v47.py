# test_v47.py - Persistent Storage Tests (NO EMOJIS)
import sys
import os
import tempfile
import time
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from storage.database import BlockchainDB
from storage.persistent_storage import PersistentStorage

def log(msg):
    sys.stdout.write(msg + "\n")

log("=" * 70)
log("v47 - PERSISTENT STORAGE + CRASH RECOVERY")
log("SQLITE + ATOMIC COMMITS + SNAPSHOTS")
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
log("\n[TEST 1] Database initialization")
with tempfile.TemporaryDirectory() as tmpdir:
    db = BlockchainDB(f"{tmpdir}/test.db")
    test("Database created", db is not None)
    test("Blocks table exists", db.get_latest_block_number() == 0)

# =========================================================
log("\n[TEST 2] Save and load block")
with tempfile.TemporaryDirectory() as tmpdir:
    db = BlockchainDB(f"{tmpdir}/test.db")
    block = {
        "hash": "0x123",
        "number": 1,
        "parent_hash": "0x000",
        "timestamp": 12345,
        "proposer": "alice",
        "state_root": "0xabc",
        "tx_root": "0xdef",
        "block_data": json.dumps({"test": "data"})
    }
    db.save_block(block)
    loaded = db.get_block("0x123")
    test("Block saved and loaded", loaded is not None)
    if loaded:
        test("Block number preserved", loaded["number"] == 1)

# =========================================================
log("\n[TEST 3] Account persistence")
with tempfile.TemporaryDirectory() as tmpdir:
    db = BlockchainDB(f"{tmpdir}/test.db")
    db.save_account("alice", 1000, 0)
    balance = db.get_balance("alice")
    test("Account saved", balance == 1000)

# =========================================================
log("\n[TEST 4] Persistent storage")
with tempfile.TemporaryDirectory() as tmpdir:
    storage = PersistentStorage(tmpdir)
    storage.save_account_state("bob", 500, 0)
    balance = storage.get_balance("bob")
    test("Persistent storage works", balance == 500)

# =========================================================
log("\n[TEST 5] Latest block tracking")
with tempfile.TemporaryDirectory() as tmpdir:
    storage = PersistentStorage(tmpdir)
    for i in range(1, 6):
        storage.save_block({"hash": f"0x{i}", "number": i, "block_data": "{}"})
    latest = storage.get_latest_block_number()
    test("Latest block number = 5", latest == 5)

# =========================================================
log("\n[TEST 6] Metadata storage")
with tempfile.TemporaryDirectory() as tmpdir:
    db = BlockchainDB(f"{tmpdir}/test.db")
    db.save_metadata("test_key", "test_value")
    value = db.get_metadata("test_key")
    test("Metadata saved and loaded", value == "test_value")

# =========================================================
log("\n[TEST 7] Validators persistence")
with tempfile.TemporaryDirectory() as tmpdir:
    db = BlockchainDB(f"{tmpdir}/test.db")
    db.save_validator("validator1", 10000)
    validators = db.get_validators()
    test("Validator saved", len(validators) >= 1)

# =========================================================
log("\n[TEST 8] Database stats")
with tempfile.TemporaryDirectory() as tmpdir:
    db = BlockchainDB(f"{tmpdir}/test.db")
    db.save_block({"hash": "0x1", "number": 1, "block_data": "{}"})
    db.save_account("alice", 1000, 0)
    stats = db.get_stats()
    test("Stats has total_blocks", "total_blocks" in stats)
    test("Stats has total_accounts", "total_accounts" in stats)

# =========================================================
log("\n[TEST 9] Crash recovery")
with tempfile.TemporaryDirectory() as tmpdir:
    storage1 = PersistentStorage(tmpdir)
    storage1.save_account_state("alice", 1000, 0)
    storage1.save_block({"hash": "0x1", "number": 1})
    
    storage2 = PersistentStorage(tmpdir)
    recovered = storage2.recover_from_crash()
    test("Crash recovery succeeds", recovered)
    test("Balance survives restart", storage2.get_balance("alice") == 1000)
    test("Block survives restart", storage2.get_latest_block_number() >= 1)

# =========================================================
log("\n[TEST 10] Snapshot creation")
with tempfile.TemporaryDirectory() as tmpdir:
    storage = PersistentStorage(tmpdir)
    result = storage.create_snapshot("0x123", 100)
    test("Snapshot created", result)
    
    snapshot = storage.restore_from_snapshot()
    test("Snapshot restored", snapshot is not None)

# =========================================================
log("\n[TEST 11] Chain exists detection")
with tempfile.TemporaryDirectory() as tmpdir:
    storage1 = PersistentStorage(tmpdir)
    test("Empty chain detection", not storage1.chain_exists())
    
    storage1.save_block({"hash": "0x1", "number": 1})
    test("Non-empty chain detection", storage1.chain_exists())

# =========================================================
log("\n[TEST 12] Backup functionality")
with tempfile.TemporaryDirectory() as tmpdir:
    storage = PersistentStorage(tmpdir)
    storage.save_account_state("alice", 1000, 0)
    backup_dir = f"{tmpdir}/backup"
    result = storage.backup(backup_dir)
    test("Backup created", result)
    test("Backup directory exists", os.path.exists(backup_dir))

# =========================================================
log("\n[TEST 13] Save metadata method")
with tempfile.TemporaryDirectory() as tmpdir:
    storage = PersistentStorage(tmpdir)
    result = storage.save_metadata("head_hash", "0xabc123")
    test("save_metadata works", result)
    value = storage.get_metadata("head_hash")
    test("get_metadata works", value == "0xabc123")

# =========================================================
log("\n[TEST 14] Account state persistence")
with tempfile.TemporaryDirectory() as tmpdir:
    storage = PersistentStorage(tmpdir)
    storage.save_account_state("charlie", 777, 42)
    account = storage.get_account_state("charlie")
    test("Account state saved", account["balance"] == 777)
    test("Nonce saved", account["nonce"] == 42)

# =========================================================
log("\n[TEST 15] Update balance")
with tempfile.TemporaryDirectory() as tmpdir:
    storage = PersistentStorage(tmpdir)
    storage.save_account_state("dave", 500, 0)
    storage.update_balance("dave", 100)
    test("Balance updated", storage.get_balance("dave") == 600)
    test("Nonce incremented", storage.get_nonce("dave") == 1)

# =========================================================
log("\n" + "=" * 70)
log(f"RESULTS: {passed}/{total} tests passed")
if passed == total:
    log("[SUCCESS] ALL TESTS PASSED!")
else:
    log(f"[WARN] Failed: {total - passed}")
log("=" * 70)
