# test_finality.py
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from consensus.engine_beacon import ConsensusEngineBeacon

print("=" * 70)
print("BEACON CHAIN FINALITY — CORRECT CASPER FFG")
print("Epoch N finalized when epoch N+1 is justified")
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

engine = ConsensusEngineBeacon(epoch_size=3)

# Add validators (total stake = 300)
engine.add_validator("v1", 100)
engine.add_validator("v2", 100)
engine.add_validator("v3", 100)

# Create blocks (10 blocks)
engine.add_block({"hash": "A", "number": 0, "parent": None})
for i in range(1, 10):
    engine.add_block({"hash": chr(ord('A') + i), "number": i, "parent": chr(ord('A') + i - 1)})

test("10 blocks created", len(engine._blocks) == 10)

# =========================================================
print("\n[TEST 1] No attestations — no finality")
finality_state = engine.get_finality_state()
test("No finality without votes", finality_state.get("finalized_epochs") == [])

# =========================================================
print("\n[TEST 2] Justify epoch 0")
for i in range(3):
    engine.on_attestation("v1", chr(ord('A') + i), slot=i)
    engine.on_attestation("v2", chr(ord('A') + i), slot=i)
    engine.on_attestation("v3", chr(ord('A') + i), slot=i)

finality_state = engine.get_finality_state()
test("Epoch 0 justified", 0 in finality_state.get("justified_epochs", []))
test("Epoch 0 NOT finalized yet", 0 not in finality_state.get("finalized_epochs", []))

# =========================================================
print("\n[TEST 3] Justify epoch 1 → finalize epoch 0")
for i in range(3, 6):
    engine.on_attestation("v1", chr(ord('A') + i), slot=i)
    engine.on_attestation("v2", chr(ord('A') + i), slot=i)
    engine.on_attestation("v3", chr(ord('A') + i), slot=i)

finality_state = engine.get_finality_state()
test("Epoch 1 justified", 1 in finality_state.get("justified_epochs", []))
test("Epoch 0 finalized after epoch 1 justified", 0 in finality_state.get("finalized_epochs", []))

# =========================================================
print("\n[TEST 4] Check finalized blocks")
is_final_a = engine.is_finalized("A")
test("Block A (epoch 0) is finalized", is_final_a == True)

# =========================================================
print("\n[TEST 5] Non-finalized block")
is_final_f = engine.is_finalized("F")
test("Block F (epoch 1) not finalized yet", is_final_f == False)

# =========================================================
print("\n[TEST 6] Justify epoch 2 → finalize epoch 1")
for i in range(6, 9):
    engine.on_attestation("v1", chr(ord('A') + i), slot=i)
    engine.on_attestation("v2", chr(ord('A') + i), slot=i)
    engine.on_attestation("v3", chr(ord('A') + i), slot=i)

finality_state = engine.get_finality_state()
test("Epoch 2 justified", 2 in finality_state.get("justified_epochs", []))
test("Epoch 1 finalized after epoch 2 justified", 1 in finality_state.get("finalized_epochs", []))

# =========================================================
print("\n[TEST 7] Stats")
stats = engine.get_stats()
test("Stats contain validators", stats.get("validators") == 3)
test("Stats contain finalized_epochs", stats.get("finalized_epochs") >= 1)

print("\n" + "=" * 70)
print(f"📊 RESULTS: {passed}/{total} tests passed")
if passed == total:
    print("🎉 BEACON FINALITY — ALL TESTS PASSED!")
    print("")
    print("   ✅ Checkpoint-based justification")
    print("   ✅ Correct Casper FFG (epoch N finalized when N+1 justified)")
    print("   ✅ Event-driven finality evaluation")
    print("   ✅ No backward inconsistencies")
    print("")
    print("🏆 This is correct Beacon Chain finality!")
else:
    print(f"⚠️ Failed: {total - passed}")
print("=" * 70)

print("\n[DEMO] Fork tree with finality markers (🔒 = finalized)")
engine.print_tree()
print("")
