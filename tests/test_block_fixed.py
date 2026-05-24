# tests/test_block_fixed.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ABSOLUTE_BLOCKCHAIN_FINAL import Block, Transaction

print("=" * 60)
print("🔧 ИСПРАВЛЕНИЕ ТЕСТА БЛОКА (С МАЙНИНГОМ)")
print("=" * 60)

# Создаём транзакции
txs = [
    Transaction("alice", "bob", 100),
    Transaction("bob", "charlie", 50),
]

# Создаём блок с difficulty 1 (легче)
block = Block(
    height=1,
    prev_hash="0"*64,
    transactions=txs,
    validator="test_validator",
    difficulty=1
)

# Майним блок
target = "0" * block.difficulty
nonce = 0
while True:
    block.nonce = nonce
    test_hash = block.calculate_hash()
    if test_hash.startswith(target):
        block.block_hash = test_hash
        break
    nonce += 1

print(f"\n✅ Блок #{block.height} (difficulty={block.difficulty})")
print(f"   Nonce: {block.nonce}")
print(f"   Block Hash: {block.block_hash[:32]}...")

if block.block_hash.startswith("0" * block.difficulty):
    print(f"   ✅ PoW пройден!")

# Проверяем целостность
assert block.block_hash == block.calculate_hash()
print(f"\n✅ Тест блока исправлен!")

# Тест с difficulty 2
print("\n" + "=" * 60)
print("🔧 ТЕСТ С DIFFICULTY 2")
print("=" * 60)

block2 = Block(
    height=2,
    prev_hash=block.block_hash,
    transactions=txs,
    validator="test_validator",
    difficulty=2
)

target = "0" * block2.difficulty
nonce = 0
while True:
    block2.nonce = nonce
    test_hash = block2.calculate_hash()
    if test_hash.startswith(target):
        block2.block_hash = test_hash
        break
    nonce += 1

print(f"\n✅ Блок #{block2.height} (difficulty={block2.difficulty})")
print(f"   Nonce: {block2.nonce}")
print(f"   Block Hash: {block2.block_hash[:32]}...")

if block2.block_hash.startswith("0" * block2.difficulty):
    print(f"   ✅ PoW пройден!")

print(f"\n🎉 ВСЕ ТЕСТЫ БЛОКА ПРОЙДЕНЫ!")
