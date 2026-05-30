# test_mev_mempool.py
import sys
import os
import builtins

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Восстанавливаем print если был переопределён
if not callable(print):
    print = builtins.print

from execution.mempool import Mempool
from execution.block_builder import BlockBuilder
from consensus.pbs import Builder, Proposer, PBSMarket

print("=" * 70)
print("MEV + MEMPOOL ECONOMY — ETHEREUM STYLE")
print("Priority fees, block builder, PBS-lite, front-running")
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
print("\n[TEST 1] Priority mempool ordering")
mempool = Mempool()

# Add transactions with different gas prices
mempool.add_tx({"hash": "tx_low", "gas_price": 1})
mempool.add_tx({"hash": "tx_high", "gas_price": 100})
mempool.add_tx({"hash": "tx_medium", "gas_price": 50})

txs = mempool.get_transactions()
test("3 transactions in mempool", len(txs) == 3)
test("Highest gas price first", txs[0].get("gas_price") == 100)
test("Lowest gas price last", txs[-1].get("gas_price") == 1)

# =========================================================
print("\n[TEST 2] Block builder")
builder = BlockBuilder(mempool)
block = builder.build_block(max_txs=3)

test("Block contains transactions", block["tx_count"] == 3)
test("Total fees calculated", block["total_fees"] == 151)

# =========================================================
print("\n[TEST 3] Gas price stats")
stats = mempool.get_stats()
test("Stats contain size", "size" in stats)
test("Stats contain max_gas_price", "max_gas_price" in stats)
test("Stats contain avg_gas_price", "avg_gas_price" in stats)

# =========================================================
print("\n[TEST 4] Front-running simulation")
builder2 = BlockBuilder(mempool)
victim = {"from": "alice", "to": "dex", "value": 100, "gas_price": 10}
attack = builder2.simulate_front_run(victim, attacker_gas_price=1000)

test("Attacker tx created", attack["attacker_tx"] is not None)
test("Attacker has higher gas price", attack["attacker_tx"]["gas_price"] > victim["gas_price"])
test("Attacker appears first", attack["result_txs"][0] == attack["attacker_tx"])

# =========================================================
print("\n[TEST 5] PBS-lite market")
pbs = PBSMarket()
pbs.add_builder(Builder("builder1"))
pbs.add_builder(Builder("builder2"))
pbs.add_proposer(Proposer("proposer1"))

transactions = [
    {"hash": "tx1", "gas_price": 100},
    {"hash": "tx2", "gas_price": 200},
    {"hash": "tx3", "gas_price": 50}
]

selected = pbs.run_auction(transactions)
test("Block selected", selected is not None)
test("Selected block has value", selected.get("value", 0) > 0)

# =========================================================
print("\n[TEST 6] Builder competition")
builder3 = Builder("builderA")
builder4 = Builder("builderB")

blockA = builder3.build_block([{"gas_price": 100}, {"gas_price": 50}])
blockB = builder4.build_block([{"gas_price": 200}])

test("BuilderA block value", blockA["total_fees"] == 150)
test("BuilderB block value", blockB["total_fees"] == 200)

# =========================================================
print("\n[TEST 7] Mempool with duplicate prevention")
mempool2 = Mempool()
result1 = mempool2.add_tx({"hash": "unique_hash", "gas_price": 10})
result2 = mempool2.add_tx({"hash": "unique_hash", "gas_price": 20})

test("First tx added", result1 == True)
test("Duplicate rejected", result2 == False)

print("\n" + "=" * 70)
print(f"📊 RESULTS: {passed}/{total} tests passed")
if passed == total:
    print("🎉 MEV + MEMPOOL ECONOMY — ALL TESTS PASSED!")
    print("")
    print("   ✅ Priority mempool (gas price ordering)")
    print("   ✅ Block builder (profit-maximizing)")
    print("   ✅ Front-running simulation")
    print("   ✅ PBS-lite (builder/proposer separation)")
    print("   ✅ Builder competition")
    print("   ✅ Duplicate protection")
    print("")
    print("🏆 Fee market and MEV layer active!")
else:
    print(f"⚠️ Failed: {total - passed}")
print("=" * 70)
