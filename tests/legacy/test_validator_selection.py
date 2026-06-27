# -*- coding: utf-8 -*-
# test_validator_selection.py
import sys
import os
import builtins

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

if not callable(print):
    print = builtins.print

from consensus.validator_selection import ValidatorSelection

print("=" * 70)
print("VALIDATOR SELECTION ? RANDAO STYLE")
print("Pseudo-random proposer selection based on chain entropy")
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
print("\n[TEST 1] Basic proposer selection")
selector = ValidatorSelection()
validators = {"v1": 100, "v2": 100, "v3": 100}

proposer1 = selector.select_proposer(validators, slot=0)
proposer2 = selector.select_proposer(validators, slot=1)

test("Proposer selected", proposer1 is not None)
test("Different slot gives different proposer", proposer1 != proposer2)

# =========================================================
print("\n[TEST 2] Seed update changes selection")
selector.update_seed("0xblock123")
proposer3 = selector.select_proposer(validators, slot=0)

test("Seed update changes selection", proposer3 != proposer1)

# =========================================================
print("\n[TEST 3] Deterministic results")
selector2 = ValidatorSelection()
selector2.update_seed("0xblock123")

proposer3_again = selector2.select_proposer(validators, slot=0)
test("Same seed gives same result", proposer3 == proposer3_again)

# =========================================================
print("\n[TEST 4] Weighted proposer selection")
selector3 = ValidatorSelection()
validators_weighted = {"v1": 1000, "v2": 100, "v3": 100}

# Run multiple times to see distribution
results = {}
for i in range(100):
    prop = selector3.select_proposer_weighted(validators_weighted, slot=i)
    results[prop] = results.get(prop, 0) + 1

test("Weighted selection works", results.get("v1", 0) > results.get("v2", 0))

# =========================================================
print("\n[TEST 5] Validator shuffling")
selector4 = ValidatorSelection()
validators_original = {"v1": 100, "v2": 100, "v3": 100}
shuffled = selector4.shuffle_validators(validators_original)

test("Shuffled has same keys", set(shuffled.keys()) == set(validators_original.keys()))
test("Shuffled order changed", list(shuffled.keys()) != list(validators_original.keys()))

# =========================================================
print("\n[TEST 6] Committee selection")
committee = selector4.get_committee(validators, committee_size=2)
test("Committee size correct", len(committee) == 2)
test("Committee members are validators", all(c in validators for c in committee))

# =========================================================
print("\n[TEST 7] Stats")
stats = selector4.get_stats()
test("Stats contain epoch", "epoch" in stats)
test("Stats contain seed", "seed" in stats)

print("\n" + "=" * 70)
print(f"?? RESULTS: {passed}/{total} tests passed")
if passed == total:
    print("?? VALIDATOR SELECTION ? ALL TESTS PASSED!")
    print("")
    print("   ? Proposer selection (deterministic pseudo-random)")
    print("   ? Weighted proposer selection (stake-based)")
    print("   ? Seed update from block hash")
    print("   ? Validator shuffling per epoch")
    print("   ? Committee selection")
    print("")
    print("?? RANDAO-style randomness active!")
else:
    print(f"?? Failed: {total - passed}")
print("=" * 70)
import sys
if __name__ == '__main__':
    raise SystemExit(0 if passed == total else 1)
