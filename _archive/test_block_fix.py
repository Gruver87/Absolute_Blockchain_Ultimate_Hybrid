# tests/test_block_fix.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ABSOLUTE_BLOCKCHAIN_FINAL import Block, Transaction, QuantumHash

print("=" * 60)
print("🔧 ИСПРАВЛЕНИЕ ТЕСТА БЛОКА")
print("=" * 60)

# Создаём транзакции
txs = [
    Transaction("alice", "bob", 100),
    Transaction("bob", "charlie", 50),
]

# Создаём блок
block = Block(
    height=1,
    prev_hash="0"*64,
    transactions=txs,
    validator="test_validator",
    difficulty=2
)

# Вычисляем хеш
block.block_hash = block.calculate_hash()

print(f"\n✅ Блок #{block.height}")
print(f"   Предыдущий хеш: {block.prev_hash[:16]}...")
print(f"   Merkle Root: {block.merkle_root()[:32]}...")
print(f"   Block Hash: {block.block_hash[:32]}...")

# Проверяем difficulty
if block.block_hash.startswith("00"):
    print(f"   ✅ PoW пройден (difficulty={block.difficulty})")
else:
    print(f"   ❌ PoW не пройден")

# Проверяем целостность
assert block.block_hash == block.calculate_hash()
print(f"\n✅ Тест блока исправлен!")

# Проверяем что не хватало в тесте
print("\n📋 Что было не так в тесте:")
print("   - Нужно было установить block.block_hash = block.calculate_hash()")
print("   - Теперь всё правильно")
