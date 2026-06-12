# test_reorg_engine.py
import sys
import os
import builtins

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# ¬осстанавливаем print если был переопределЄн
if not callable(print):
    print = builtins.print

from consensus.reorg_engine import ReorgEngine

print("=" * 70)
print("REORG ENGINE Ч FINALITY-SAFE CONSENSUS")
print("Finalized blocks cannot be reverted")
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
print("\n[SETUP] Building blockchain")
engine = ReorgEngine()

# Chain A: A0 > A1 > A2 > A3
engine.add_block("A0", None, 0)
engine.add_block("A1", "A0", 1)
engine.add_block("A2", "A1", 2)
engine.add_block("A3", "A2", 3)

# Chain B (fork): A0 > B1 > B2
engine.add_block("B1", "A0", 1)
engine.add_block("B2", "B1", 2)

engine.set_head("A3")

test("Head set to A3", engine.get_head() == "A3")

# =========================================================
print("\n[TEST 1] Valid reorg (no finalized blocks)")
# Reorg from A3 to B2 (both are valid, no finality violation)
result = engine.try_reorg("B2")
test("Reorg to B2 allowed", result == True)
test("New head is B2", engine.get_head() == "B2")

# Reorg back to A3
result = engine.try_reorg("A3")
test("Reorg back to A3 allowed", result == True)

# =========================================================
print("\n[TEST 2] Finalized block protection")
# Finalize block A1
engine.set_finalized("A1")

# Try to reorg to a chain that doesn't include A1
result = engine.try_reorg("B2")
test("Reorg to B2 blocked (A1 finalized)", result == False)
test("Head unchanged", engine.get_head() == "A3")

# =========================================================
print("\n[TEST 3] Reorg to chain containing finalized block")
# Create chain that includes A1
engine.add_block("C1", "A1", 2)
engine.add_block("C2", "C1", 3)

result = engine.try_reorg("C2")
test("Reorg to chain containing A1 allowed", result == True)
test("New head is C2", engine.get_head() == "C2")

# =========================================================
print("\n[TEST 4] Chain from head")
chain = engine.get_chain_from_head()
test("Chain includes genesis", "A0" in chain)
test("Chain includes A1 (finalized)", "A1" in chain)
test("Chain includes C2 (head)", "C2" == chain[-1])

# =========================================================
print("\n[TEST 5] Stats")
stats = engine.get_stats()
test("Stats contain head", "head" in stats)
test("Stats contain finalized_blocks", "finalized_blocks" in stats)
test("Stats contain total_blocks", "total_blocks" in stats)

print("\n" + "=" * 70)
print(f"?? RESULTS: {passed}/{total} tests passed")
if passed == total:
    print("?? REORG ENGINE Ч ALL TESTS PASSED!")
    print("")
    print("   ? Finalized blocks cannot be reverted")
    print("   ? Safe reorg detection")
    print("   ? Reorg blocking when crossing finality")
    print("   ? Chain reconstruction from head")
    print("   ? Finality protection works")
    print("")
    print("?? Reorg safety layer active!")
else:
    print(f"?? Failed: {total - passed}")
print("=" * 70)

print("\n[DEMO] Finality protection")
print("   Chain A: A0 > A1 > A2 > A3")
print("   Chain B: A0 > B1 > B2")
print("   After A1 is finalized:")
print("   > Reorg to Chain B is BLOCKED")
print("   > Reorg to Chain containing A1 is ALLOWED")
print("")
