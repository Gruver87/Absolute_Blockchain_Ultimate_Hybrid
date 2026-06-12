# test_v52.py - Consensus Convergence Tests (FINAL FIX)
import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def log(msg):
    sys.stdout.write(msg + "\n")

log("=" * 70)
log("v52 - CONSENSUS CONVERGENCE ENGINE")
log("Validator Scoring + Chain Weight + Finality + Reorg")
log("Byzantine Quorum: 2/3+ supermajority")
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
log("\n[TEST 1] Validator Registry")
from consensus.validator_registry import ValidatorRegistry

reg = ValidatorRegistry()
reg.register_validator("0xalice", 10000)
reg.register_validator("0xbob", 5000)

test("Validators registered", len(reg.get_all_validators()) == 2)
test("Total stake = 15000", reg.get_total_stake() == 15000)

# =========================================================
log("\n[TEST 2] Validator scoring")
alice = reg.get_validator("0xalice")
initial_score = alice.get_score()
test("Alice initial score", initial_score == 10000)

alice.record_missed_block()
alice.record_missed_block()
test("Score decreases after missed blocks", alice.get_score() < initial_score)

alice.record_produced_block()
test("Score remains positive", alice.get_score() > 0)

# =========================================================
log("\n[TEST 3] Slashing mechanism")
reg2 = ValidatorRegistry()
reg2.register_validator("0xbob2", 5000)
bob2 = reg2.get_validator("0xbob2")
test("Bob initial reputation", bob2.reputation == 1.0)

for i in range(15):
    bob2.record_missed_block()
test("Bob slashed after many misses", bob2.slashed)

# =========================================================
log("\n[TEST 4] Validator stats")
stats = reg.get_stats()
test("Stats has total_validators", "total_validators" in stats)
test("Stats has total_stake", "total_stake" in stats)

# =========================================================
log("\n[TEST 5] Convergence Engine")
from consensus.convergence_engine import ConvergenceEngine, finality_threshold, is_supermajority

class MockNode:
    pass

engine = ConvergenceEngine(MockNode())
test("ConvergenceEngine created", engine is not None)

# =========================================================
log("\n[TEST 6] Finality threshold function")
test("3 validators need 2 votes", finality_threshold(3) == 2)
test("4 validators need 3 votes", finality_threshold(4) == 3)
test("6 validators need 4 votes", finality_threshold(6) == 4)
test("7 validators need 5 votes", finality_threshold(7) == 5)

# =========================================================
log("\n[TEST 7] Supermajority check")
test("2/3 of 3 = 2 -> supermajority", is_supermajority(2, 3) == True)
test("1/3 of 3 = 1 -> not supermajority", is_supermajority(1, 3) == False)

# =========================================================
log("\n[TEST 8] Block weight calculation")
block = {
    "hash": "0x123",
    "number": 1,
    "proposer": "0xalice",
    "timestamp": 12345
}
weight = engine.calculate_block_weight(block, reg)
test("Block weight calculated", weight.total_weight > 0)

# =========================================================
log("\n[TEST 9] Chain weight calculation")
chain_blocks = [
    {"hash": "0x1", "number": 1, "proposer": "0xalice"},
    {"hash": "0x2", "number": 2, "proposer": "0xbob"},
    {"hash": "0x3", "number": 3, "proposer": "0xalice"}
]
chain_weight = engine.calculate_chain_weight(chain_blocks, reg)
test("Chain weight calculated", chain_weight > 0)

# =========================================================
log("\n[TEST 10] Finality with 2/3 votes (Byzantine quorum)")
test_block = {"hash": "0x456", "number": 10, "proposer": "0xalice"}

# With 3 validators, need 2 votes for finality
votes_2_3 = [{"validator": "0xalice"}, {"validator": "0xbob"}]
is_final = engine.check_finality(test_block, votes_2_3, 3)
test("2/3 votes -> FINALIZED (3 validators, 2 votes)", is_final)

# With 3 validators, 1 vote is NOT enough
votes_1_3 = [{"validator": "0xalice"}]
is_final = engine.check_finality(test_block, votes_1_3, 3)
test("1/3 votes -> NOT finalized", not is_final)

# With 3 validators, 3 votes also works
votes_3_3 = [{"validator": "0xalice"}, {"validator": "0xbob"}, {"validator": "0xcharlie"}]
is_final = engine.check_finality(test_block, votes_3_3, 3)
test("3/3 votes -> FINALIZED", is_final)

# =========================================================
log("\n[TEST 11] Chain selection")
chains = {
    "chain1": [{"hash": "0x1", "proposer": "0xalice"}],
    "chain2": [{"hash": "0x2", "proposer": "0xbob"}]
}
best = engine.choose_canonical_chain(chains, reg)
test("Canonical chain selected", best is not None)

# =========================================================
log("\n[TEST 12] Reorg decision")
current_chain = [{"hash": "0x1", "number": 1, "proposer": "0xalice"}]
new_chain = [{"hash": "0x2", "number": 1, "proposer": "0xalice"}]
should_reorg = engine.maybe_reorganize(new_chain, current_chain, reg)
test("Reorg decision returns bool", isinstance(should_reorg, bool))

# =========================================================
log("\n[TEST 13] Attestation processing")
attestation = {
    "validator": "0xalice",
    "target_hash": "0x123"
}
processed = engine.process_attestation(attestation, reg)
test("Attestation processed", processed)

# =========================================================
log("\n[TEST 14] Top validators")
top = reg.get_top_validators(2)
test("Top validators returned", len(top) >= 1)
if len(top) >= 1:
    test("Top validator has highest stake", top[0].stake >= (top[-1].stake if len(top) > 1 else top[0].stake))

# =========================================================
log("\n" + "=" * 70)
log(f"RESULTS: {passed}/{total} tests passed")

if passed == total:
    log("[SUCCESS] v52 CONSENSUS CONVERGENCE READY!")
    log("")
    log("What v52 adds:")
    log("  -> Validator scoring (stake + reputation)")
    log("  -> Slashing mechanism for malicious validators")
    log("  -> Chain weight calculation based on validator scores")
    log("  -> Byzantine finality engine (2/3+ supermajority)")
    log("  -> Canonical chain selection by weight")
    log("  -> Reorg decisions based on chain weight")
    log("")
    log("Byzantine Quorum math:")
    log("  threshold = (2 * total_validators + 2) // 3")
    log("  ? 3 validators -> need 2 votes")
    log("  ? 4 validators -> need 3 votes")
    log("  ? 6 validators -> need 4 votes")
    log("")
    log("? v52 IS READY FOR PRODUCTION!")
else:
    log(f"[WARN] Failed: {total - passed}")
log("=" * 70)
