# test_merkle_light.py
import sys
import os
import builtins

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

if not callable(print):
    print = builtins.print

from crypto.merkle import merkle_root, generate_proof, verify_proof, merkle_root_from_proof
from core.block_header import FullBlock
from light.light_client import LightClient

print("=" * 70)
print("MERKLE TREE + LIGHT CLIENT")
print("Transaction proofs, header-only verification")
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
print("\n[TEST 1] Merkle root computation")
transactions = ["tx1", "tx2", "tx3", "tx4"]
root = merkle_root(transactions)
test("Root computed", len(root) == 64)

# Same transactions should give same root
root2 = merkle_root(transactions)
test("Deterministic", root == root2)

# Different transactions give different root
root3 = merkle_root(["tx1", "tx2", "tx3", "tx5"])
test("Different txs change root", root != root3)

# =========================================================
print("\n[TEST 2] Merkle proof generation")
txs = ["A", "B", "C", "D", "E", "F", "G", "H"]
target_tx = "C"
target_index = 2  # "C" at index 2

proof = generate_proof(txs, target_index)
test("Proof generated", len(proof) > 0)

# Verify proof
is_valid = verify_proof(target_tx, proof, merkle_root(txs), target_index)
test("Valid proof works", is_valid == True)

# Modified tx should fail
is_valid_fake = verify_proof("FAKE", proof, merkle_root(txs), target_index)
test("Modified tx fails", is_valid_fake == False)

# =========================================================
print("\n[TEST 3] Reconstruct root from proof")
reconstructed_root = merkle_root_from_proof(target_tx, proof, target_index)
test("Reconstructed root matches original", reconstructed_root == merkle_root(txs))

# =========================================================
print("\n[TEST 4] Block with Merkle root")
block = FullBlock.create(
    number=1,
    parent_hash="0xgenesis",
    proposer="validator1",
    state_root="0xstate",
    transactions=[
        {"from": "alice", "to": "bob", "amount": 100},
        {"from": "alice", "to": "charlie", "amount": 50},
        {"from": "bob", "to": "alice", "amount": 25}
    ]
)

test("Block created", block is not None)
test("Tx root computed", len(block.header.tx_root) == 64)
test("Tx root not empty", block.header.tx_root != merkle_root([]))

# =========================================================
print("\n[TEST 5] Light client")
light = LightClient()
light.add_header(block.header)

test("Header stored", light.get_header_count() == 1)
test("Latest header accessible", light.get_latest_header() is not None)
test("Header number correct", light.get_latest_header().number == 1)

# =========================================================
print("\n[TEST 6] Light client transaction verification")
# Get specific transaction and generate proof
txs_for_proof = [
    {"from": "alice", "to": "bob", "amount": 100},
    {"from": "alice", "to": "charlie", "amount": 50},
    {"from": "bob", "to": "alice", "amount": 25}
]
target_tx_dict = {"from": "bob", "to": "alice", "amount": 25}
target_idx = 2

import json
tx_strings = [json.dumps(tx, sort_keys=True) for tx in txs_for_proof]
tx_root = merkle_root(tx_strings)
proof = generate_proof(tx_strings, target_idx)

is_valid = light.verify_transaction(target_tx_dict, tx_root, proof, target_idx)
test("Light client verifies tx", is_valid == True)

# Invalid tx
fake_tx = {"from": "hacker", "to": "alice", "amount": 1000}
is_valid_fake = light.verify_transaction(fake_tx, tx_root, proof, target_idx)
test("Light client rejects fake tx", is_valid_fake == False)

# =========================================================
print("\n[TEST 7] Empty merkle root")
empty_root = merkle_root([])
test("Empty root computed", empty_root is not None)
test("Empty root length 64", len(empty_root) == 64)

print("\n" + "=" * 70)
print(f"📊 RESULTS: {passed}/{total} tests passed")
if passed == total:
    print("🎉 MERKLE + LIGHT CLIENT — ALL TESTS PASSED!")
    print("")
    print("   ✅ Merkle root computation")
    print("   ✅ Proof generation")
    print("   ✅ Proof verification")
    print("   ✅ Root reconstruction from proof")
    print("   ✅ Block with transaction root")
    print("   ✅ Light client header storage")
    print("   ✅ Transaction verification without full block")
    print("")
    print("🏆 Light client and Merkle proofs ready!")
else:
    print(f"⚠️ Failed: {total - passed}")
print("=" * 70)
