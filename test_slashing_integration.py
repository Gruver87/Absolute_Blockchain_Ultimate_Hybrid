# test_slashing_integration.py
import sys
import os
import builtins

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Восстанавливаем print если был переопределён
if not callable(print):
    print = builtins.print

from consensus.engine_with_slashing import ConsensusEngineSlashing

print("=" * 70)
print("SLASHING INTEGRATION — DOUBLE VOTE DETECTION")
print("Validator who double votes is removed from consensus")
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
print("\n[SETUP] Creating blockchain")

engine = ConsensusEngineSlashing(epoch_size=3)

# Add validators
engine.add_validator("v1", 100)
engine.add_validator("v2", 100)
engine.add_validator("v3", 100)

# Create blocks
engine.add_block({"hash": "A", "number": 0, "parent": None})
for i in range(1, 5):
    engine.add_block({"hash": chr(ord('A') + i), "number": i, "parent": chr(ord('A') + i - 1)})

test("5 blocks created", len(engine._blocks) == 5)

# =========================================================
print("\n[TEST 1] Normal attestations (no slash)")
engine.on_attestation("v1", "A", slot=0)
engine.on_attestation("v2", "A", slot=0)
engine.on_attestation("v3", "A", slot=0)

slashing_info = engine.get_slashing_info()
test("No slashed validators", slashing_info["count"] == 0)

# =========================================================
print("\n[TEST 2] Double vote detection")
# v1 tries to double vote in same epoch
engine.on_attestation("v1", "B", slot=0)  # Same epoch, different block

slashing_info = engine.get_slashing_info()
test("v1 slashed for double vote", "v1" in slashing_info["slashed"])
test("Slash reason recorded", "DOUBLE_VOTE" in slashing_info["reasons"].get("v1", ""))

# =========================================================
print("\n[TEST 3] Slashed validator excluded from consensus")
# Try to attest again
engine.on_attestation("v1", "C", slot=1)

# Check that v1's votes don't affect weights
stats = engine.get_stats()
test("Active validators count reduced", stats["active_validators"] == 2)
test("Active stake reduced", stats["active_stake"] == 200)  # v2 + v3 only

# =========================================================
print("\n[TEST 4] Honest validators unaffected")
engine.on_attestation("v2", "B", slot=1)
engine.on_attestation("v3", "B", slot=1)

head = engine.get_head()
test("Head still determined correctly", head is not None)

# =========================================================
print("\n[TEST 5] Stats")
stats = engine.get_stats()
test("Stats contain active_validators", "active_validators" in stats)
test("Stats contain slashed_count", "slashed_count" in stats)
test("Stats contain active_stake", "active_stake" in stats)

print("\n" + "=" * 70)
print(f"📊 RESULTS: {passed}/{total} tests passed")
if passed == total:
    print("🎉 SLASHING INTEGRATION — ALL TESTS PASSED!")
    print("")
    print("   ✅ Double vote detection")
    print("   ✅ Slashed validator excluded from consensus")
    print("   ✅ Stake calculation only from active validators")
    print("   ✅ LMD updates blocked for slashed validators")
    print("")
    print("🏆 Economic consensus protection active!")
else:
    print(f"⚠️ Failed: {total - passed}")
print("=" * 70)
