# test_adversarial_network.py
import sys
import os
import time
import builtins

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# ¬осстанавливаем print если был переопределЄн
if not callable(print):
    print = builtins.print

from network.adversarial_network import AdversarialNetwork

print("=" * 70)
print("ADVERSARIAL NETWORK Ч HOSTILE CONDITIONS")
print("Delays, partitions, message loss, fork injection")
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
print("\n[TEST 1] Basic message delivery")
net = AdversarialNetwork()
net.add_node("A")
net.add_node("B")
net.set_latency("A", "B", 0.01, 0.05)

result = net.send("A", "B", {"type": "test", "data": "hello"})
test("Message accepted", result == True)

delivered = net.process(time.time() + 0.06)
test("Message delivered after delay", len(delivered) == 1)

# =========================================================
print("\n[TEST 2] Message loss")
net2 = AdversarialNetwork()
net2.add_node("A")
net2.add_node("B")
net2.set_loss_rate(0.5)  # 50% loss

sent = 0
for i in range(100):
    if net2.send("A", "B", {"type": "test", "data": i}):
        sent += 1

test("Some messages lost", sent < 100)
test("Not all messages lost", sent > 0)

# =========================================================
print("\n[TEST 3] Network partition")
net3 = AdversarialNetwork()
for node in ["A", "B", "C", "D"]:
    net3.add_node(node)

net3.partition([["A", "B"], ["C", "D"]])

test("A and B connected", net3.is_connected("A", "B") == True)
test("A and C disconnected", net3.is_connected("A", "C") == False)
test("C and D connected", net3.is_connected("C", "D") == True)

# =========================================================
print("\n[TEST 4] Partition healing")
net3.clear_partition()
test("After healing, A and C connected", net3.is_connected("A", "C") == True)

# =========================================================
print("\n[TEST 5] Fork injection")
net4 = AdversarialNetwork()
net4.add_node("victim")
net4.inject_fake_block("victim", {"hash": "0xfake", "number": 100})

fake_blocks = net4.get_fake_blocks("victim")
test("Fake block injected", len(fake_blocks) == 1)
test("Fake block content correct", fake_blocks[0].get("hash") == "0xfake")

# =========================================================
print("\n[TEST 6] Stats")
stats = net4.get_stats()
test("Stats contain nodes", "nodes" in stats)
test("Stats contain partitions", "partitions" in stats)
test("Stats contain loss_rate", "loss_rate" in stats)

print("\n" + "=" * 70)
print(f"?? RESULTS: {passed}/{total} tests passed")
if passed == total:
    print("?? ADVERSARIAL NETWORK Ч ALL TESTS PASSED!")
    print("")
    print("   ? Message delay simulation")
    print("   ? Message loss (50% rate)")
    print("   ? Network partition (isolated groups)")
    print("   ? Partition healing")
    print("   ? Fork injection attack")
    print("   ? Statistics tracking")
    print("")
    print("?? Hostile network conditions ready!")
else:
    print(f"?? Failed: {total - passed}")
print("=" * 70)

print("\n[DEMO] Network partition scenario")
print("   Group 1: A, B")
print("   Group 2: C, D")
print("   Messages between groups are dropped")
print("   After healing, communication restored")
print("")
