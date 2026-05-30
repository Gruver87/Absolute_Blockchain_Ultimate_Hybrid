# test_state_engine.py
import sys
import os
import builtins

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Восстанавливаем print если был переопределён
if not callable(print):
    print = builtins.print

from execution.state_engine import StateEngine

print("=" * 70)
print("STATE ENGINE — MINI EXECUTION LAYER")
print("Transactions, checkpoints, state roots, rollback")
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
print("\n[TEST 1] Basic balance operations")
engine = StateEngine()
engine.set_balance("alice", 1000)
engine.set_balance("bob", 0)

test("Alice balance 1000", engine.get_balance("alice") == 1000)
test("Bob balance 0", engine.get_balance("bob") == 0)

# =========================================================
print("\n[TEST 2] Transaction execution")
tx = {"from": "alice", "to": "bob", "value": 100}
result = engine.apply_transaction(tx)

test("Transaction success", result == True)
test("Alice balance decreased", engine.get_balance("alice") == 900)
test("Bob balance increased", engine.get_balance("bob") == 100)

# =========================================================
print("\n[TEST 3] Insufficient balance")
tx2 = {"from": "alice", "to": "bob", "value": 1000}
result2 = engine.apply_transaction(tx2)

test("Insufficient balance rejected", result2 == False)
test("Balances unchanged", engine.get_balance("alice") == 900)

# =========================================================
print("\n[TEST 4] Block application")
engine2 = StateEngine()
engine2.set_balance("alice", 1000)

block = {
    "hash": "0xblock1",
    "transactions": [
        {"from": "alice", "to": "bob", "value": 100},
        {"from": "alice", "to": "charlie", "value": 50}
    ]
}

result = engine2.apply_block(block)
test("Block applied successfully", result == True)
test("Bob received 100", engine2.get_balance("bob") == 100)
test("Charlie received 50", engine2.get_balance("charlie") == 50)
test("Alice balance after txs", engine2.get_balance("alice") == 850)

# =========================================================
print("\n[TEST 5] Checkpoint and rollback")
engine3 = StateEngine()
engine3.set_balance("alice", 1000)

# Сохраняем checkpoint
engine3.create_checkpoint("checkpoint_1")
test("Checkpoint created", "checkpoint_1" in engine3.checkpoints)

# Изменяем состояние
engine3.apply_transaction({"from": "alice", "to": "bob", "value": 100})
test("After tx, Alice has 900", engine3.get_balance("alice") == 900)

# Откатываем
engine3.rollback("checkpoint_1")
test("After rollback, Alice has 1000", engine3.get_balance("alice") == 1000)

# =========================================================
print("\n[TEST 6] State root")
engine4 = StateEngine()
engine4.set_balance("alice", 100)
engine4.set_balance("bob", 200)

root1 = engine4.compute_state_root()
test("State root computed", len(root1) == 64)

engine4.set_balance("charlie", 300)
root2 = engine4.compute_state_root()
test("State root changes after state change", root1 != root2)

# =========================================================
print("\n[TEST 7] Stats")
stats = engine4.get_stats()
test("Stats contain accounts", "accounts" in stats)
test("Stats contain total_supply", "total_supply" in stats)
test("Stats contain checkpoints", "checkpoints" in stats)

print("\n" + "=" * 70)
print(f"📊 RESULTS: {passed}/{total} tests passed")
if passed == total:
    print("🎉 STATE ENGINE — ALL TESTS PASSED!")
    print("")
    print("   ✅ Balance management")
    print("   ✅ Transaction execution")
    print("   ✅ Insufficient balance protection")
    print("   ✅ Block application")
    print("   ✅ Checkpoint and rollback")
    print("   ✅ State root computation")
    print("")
    print("🏆 State layer active!")
else:
    print(f"⚠️ Failed: {total - passed}")
print("=" * 70)
