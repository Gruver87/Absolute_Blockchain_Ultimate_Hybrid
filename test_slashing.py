# test_slashing.py
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from consensus.slashing import SlashingEngine, SlashingReason

print("=" * 70)
print("SLASHING ENGINE — DOUBLE VOTE + SURROUND VOTE")
print("Экономическая защита консенсуса")
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
print("\n[TEST 1] Basic slashing registration")
slasher = SlashingEngine(initial_stake=100)
slasher.register_validator("alice", 100)
slasher.register_validator("bob", 100)

test("Validators registered", slasher.get_total_active_stake() == 200)

# =========================================================
print("\n[TEST 2] Normal vote (no slash)")
result = slasher.add_vote("alice", epoch=1, block_hash="0xABC")
test("Normal vote accepted", result == True)
test("No slash recorded", len(slasher.slashed_validators) == 0)

# =========================================================
print("\n[TEST 3] Double vote detection")
# Same validator, same epoch, different block
result2 = slasher.add_vote("alice", epoch=1, block_hash="0xDEF")
test("Double vote detected and rejected", result2 == False)
test("Validator slashed", "alice" in slasher.slashed_validators)

# Check slashed validators stats
stats = slasher.get_stats()
test("Slashed validators count", stats["slashed_validators"] == 1)
test("Active stake reduced", stats["active_stake"] == 100)  # only bob remains

# =========================================================
print("\n[TEST 4] New validator cannot vote after slash")
result3 = slasher.add_vote("alice", epoch=2, block_hash="0xGHI")
test("Slashed validator votes rejected", result3 == False)

# =========================================================
print("\n[TEST 5] Surround vote detection")
slasher2 = SlashingEngine(initial_stake=100)
slasher2.register_validator("carol", 100)

# First vote in epoch 1
slasher2.add_vote("carol", epoch=1, block_hash="0xBLOCK_A")

# Second vote in epoch 3 (surrounds by being later on different branch)
# This simulates a surround vote attack
result4 = slasher2.add_vote("carol", epoch=3, block_hash="0xBLOCK_B")
test("Surround vote detected", result4 == False)
test("Validator slashed for surround vote", "carol" in slasher2.slashed_validators)

# Check reason
reason = slasher2.get_slash_reason("carol")
test("Slash reason is surround_vote", reason == SlashingReason.SURROUND_VOTE.value)

# =========================================================
print("\n[TEST 6] Stats")
stats2 = slasher2.get_stats()
test("Stats contains total_validators", "total_validators" in stats2)
test("Stats contains slashed_validators", "slashed_validators" in stats2)
test("Stats contains slashed_stake", "slashed_stake" in stats2)

print("\n" + "=" * 70)
print(f"📊 RESULTS: {passed}/{total} tests passed")
if passed == total:
    print("🎉 SLASHING ENGINE — ALL TESTS PASSED!")
    print("")
    print("   ✅ Double vote detection")
    print("   ✅ Surround vote detection")
    print("   ✅ Stake slashing")
    print("   ✅ Slashed validator exclusion from consensus")
    print("   ✅ Statistics tracking")
    print("")
    print("🏆 Economic consensus protection active!")
else:
    print(f"⚠️ Failed: {total - passed}")
print("=" * 70)
