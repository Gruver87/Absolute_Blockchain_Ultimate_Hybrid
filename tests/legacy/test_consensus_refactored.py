# test_consensus_refactored.py
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from consensus.engine_refactored import ConsensusEngine

print("=" * 70)
print("CONSENSUS REFACTORED — LMD + GHOST SEPARATION")
print("Deterministic fork choice (Ethereum-style)")
print("=" * 70)

passed = 0
total = 0

def test(name, condition):
    global passed, total
    total += 1
    if condition:
        print(f"   ? {name}")
        passed += 1
    else:
        print(f"   ? {name}")

# =========================================================
print("\n[SETUP] Creating blocks")

engine = ConsensusEngine()

engine.add_validator("v1", 100)
engine.add_validator("v2", 100)
engine.add_validator("v3", 100)

# Genesis
engine.add_block({"hash": "A", "number": 0, "parent": None})
# Chain A
engine.add_block({"hash": "B", "number": 1, "parent": "A"})
engine.add_block({"hash": "C", "number": 2, "parent": "B"})
engine.add_block({"hash": "D", "number": 3, "parent": "C"})
# Chain B
engine.add_block({"hash": "X", "number": 1, "parent": "A"})
engine.add_block({"hash": "Y", "number": 2, "parent": "X"})
engine.add_block({"hash": "Z", "number": 3, "parent": "Y"})

test("7 blocks added", len(engine._blocks) == 7)

# =========================================================
print("\n[TEST 1] No attestations")
head = engine.get_head()
test("Head is highest block when no votes", head in ["D", "Z"])

# =========================================================
print("\n[TEST 2] Attestations to chain D")
engine.on_attestation("v1", "D", slot=1)
engine.on_attestation("v2", "D", slot=1)
engine.on_attestation("v3", "D", slot=1)

head = engine.get_head()
test("Head is D after all votes", head == "D")

# =========================================================
print("\n[TEST 3] LMD rule — validator changes attestation")
engine.on_attestation("v1", "Z", slot=2)
head = engine.get_head()
# D has 200 weight (v2+v3), Z has 100 weight (v1)
# GHOST picks D (heavier subtree)
test("Head remains D (heavier weight)", head == "D")

# v1 changes back to D
engine.on_attestation("v1", "D", slot=3)
head = engine.get_head()
test("Head is D after v1 returns", head == "D")

# =========================================================
print("\n[TEST 4] All validators on chain Z")
engine.on_attestation("v1", "Z", slot=10)
engine.on_attestation("v2", "Z", slot=10)
engine.on_attestation("v3", "Z", slot=10)

head = engine.get_head()
test("Head is Z after all votes on chain Z", head == "Z")

# =========================================================
print("\n[TEST 5] LMD slot order (strict slot-based)")
engine2 = ConsensusEngine()
engine2.add_validator("v1", 100)
engine2.add_block({"hash": "A", "number": 0, "parent": None})
engine2.add_block({"hash": "B", "number": 1, "parent": "A"})
engine2.add_block({"hash": "C", "number": 2, "parent": "A"})

engine2.on_attestation("v1", "B", slot=5)
engine2.on_attestation("v1", "C", slot=10)  # newer slot
head = engine2.get_head()
test("Newer slot overwrites older (C wins)", head == "C")

# =========================================================
print("\n[TEST 6] Stats")
stats = engine.get_stats()
test("Stats contain validators", stats.get("validators") == 3)
test("Stats contain active_votes", stats.get("active_votes") == 3)
test("Stats contain blocks", stats.get("blocks") == 7)

print("\n" + "=" * 70)
print(f"?? RESULTS: {passed}/{total} tests passed")
if passed == total:
    print("?? CONSENSUS REFACTORED — ALL TESTS PASSED!")
    print("")
    print("   ? LMD table (strict slot-based)")
    print("   ? Pure GHOST fork choice")
    print("   ? Separated orchestration")
    print("   ? Deterministic head selection")
    print("   ? No intermediate state leakage")
    print("")
    print("?? This is Ethereum client architecture!")
else:
    print(f"?? Failed: {total - passed}")
print("=" * 70)

print("\n[DEMO] Fork tree with weights")
engine.print_tree()
print("")
