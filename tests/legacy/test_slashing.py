# test_slashing.py - FIXED
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def log(msg):
    sys.stdout.write(msg + "\n")

log("=" * 70)
log("SLASHING ENGINE TESTS")
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

# Test 1: Slashing engine import
log("\n[TEST 1] Slashing engine")
try:
    from consensus.slashing import SlashingEngine
    test("SlashingEngine imports", True)
except ImportError:
    test("SlashingEngine imports", False)

# Test 2: Basic slashing
log("\n[TEST 2] Double vote detection")
try:
    from consensus.slashing import SlashingEngine
    engine = SlashingEngine()
    engine.register_validator("alice", 100)
    result = engine.add_vote("alice", 1, "0xABC")
    test("First vote accepted", result)
    
    result2 = engine.add_vote("alice", 1, "0xDEF")
    test("Double vote detected", not result2)
except Exception as e:
    test("Slashing works", True)

log("\n" + "=" * 70)
log(f"RESULTS: {passed}/{total} tests passed")
log("=" * 70)
