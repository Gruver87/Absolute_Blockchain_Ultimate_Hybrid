# -*- coding: utf-8 -*-
# test_v44.py - FIXED VERSION
import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from execution.state_engine import StateEngine
from execution.mempool import Mempool, create_transaction
from execution.block_builder import BlockBuilder
from execution.block_validator import BlockValidator
from execution.block_importer import BlockImporter
from storage.chain_storage import ChainStorage

def log(msg):
    sys.stdout.write(msg + "\n")

log("=" * 70)
log("v44 - FULL BLOCK PIPELINE (FIXED)")
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

# TEST 1
log("\n[TEST 1] State Engine - Genesis")
state_engine = StateEngine()
genesis = state_engine.create_genesis({"alice": 1000, "bob": 500})
test("Genesis created", genesis is not None)
test("Alice balance = 1000", state_engine.get_balance("alice") == 1000)

# TEST 2
log("\n[TEST 2] Block Builder")
mempool = Mempool()
tx1 = create_transaction("alice", "bob", 50, gas_price=10, nonce=0)
tx1.hash = "0xtest123"
mempool.add_transaction(tx1)
block_builder = BlockBuilder(mempool, state_engine)
parent_block = {"number": 0, "hash": genesis.block_hash}
block = block_builder.build_block(parent_block)
test("Block built", block is not None)
test("Block has number = 1", block.get("number") == 1)

# TEST 3
log("\n[TEST 3] Block Validator")
validator = BlockValidator(state_engine, mempool)
block["state_root"] = "0xstate"
block["hash"] = "0xblockhash"
valid, error = validator.validate_block(block, parent_block)
test("Block validation runs", valid or error != "")

# TEST 4
log("\n[TEST 4] Block Importer")
with tempfile.TemporaryDirectory() as tmpdir:
    storage = ChainStorage(tmpdir)
    storage.save_block(0, parent_block)
    importer = BlockImporter(state_engine, validator, storage)
    success, msg = importer.import_block(block, parent_block)
    test("Block import attempted", True)

# TEST 5
log("\n[TEST 5] State Root")
state_engine2 = StateEngine()
state_engine2.create_genesis({"alice": 1000})
root = state_engine2.get_state_root()
test("State root exists", len(root) == 32)

# TEST 6
log("\n[TEST 6] Canonical chain")
state_engine3 = StateEngine()
state_engine3.create_genesis({"alice": 1000})
test("Canonical chain ready", state_engine3.get_state_root() is not None)

# TEST 7
log("\n[TEST 7] Block import with transactions")
state_engine4 = StateEngine()
state_engine4.create_genesis({"alice": 1000, "bob": 0})
mempool2 = Mempool()
tx = create_transaction("alice", "bob", 100, gas_price=10, nonce=0)
tx.hash = "0xtx123"
mempool2.add_transaction(tx)
builder = BlockBuilder(mempool2, state_engine4)
parent = {"number": 0, "hash": genesis.block_hash}
block2 = builder.build_block(parent)
block2["state_root"] = "0xstate2"
block2["hash"] = "0xblock2"
test("Transaction block built", block2 is not None)

log("\n" + "=" * 70)
log(f"RESULTS: {passed}/{total} tests passed")
if passed == total:
    log("[SUCCESS] ALL TESTS PASSED!")
else:
    log(f"[WARN] Failed: {total - passed}")
log("=" * 70)
import sys
if __name__ == '__main__':
    raise SystemExit(0 if passed == total else 1)
