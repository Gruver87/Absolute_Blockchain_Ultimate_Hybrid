# tests/test_blockchain.py
# ПОЛНОЕ ТЕСТИРОВАНИЕ ВСЕХ КОМПОНЕНТОВ

import sys
import os
import time
import json
import hashlib

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ============================================================================
# 1. ТЕСТ QUANTUM HASH
# ============================================================================

def test_quantum_hash():
    print("\n" + "=" * 60)
    print("🧪 ТЕСТ 1: QUANTUM HASH ENGINE")
    print("=" * 60)
    
    try:
        from ABSOLUTE_BLOCKCHAIN_FINAL import QuantumHash
        
        test_data = "Hello, Blockchain!"
        hash1 = QuantumHash.hash(test_data)
        hash2 = QuantumHash.hash(test_data)
        
        assert len(hash1) == 64, f"Hash length error: {len(hash1)}"
        assert hash1 == hash2, "Hash not deterministic"
        
        print(f"✅ Quantum Hash: {hash1[:32]}...")
        print(f"✅ Длина хеша: {len(hash1)} символов")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

# ============================================================================
# 2. ТЕСТ MERKLE TREE
# ============================================================================

def test_merkle_root():
    print("\n" + "=" * 60)
    print("🧪 ТЕСТ 2: MERKLE TREE")
    print("=" * 60)
    
    try:
        from ABSOLUTE_BLOCKCHAIN_FINAL import QuantumHash, Transaction
        
        txs = [
            Transaction("alice", "bob", 100),
            Transaction("bob", "charlie", 50),
            Transaction("charlie", "david", 25),
        ]
        
        tx_hashes = [tx.hash() for tx in txs]
        merkle = QuantumHash.merkle_root(tx_hashes)
        
        assert len(merkle) == 64, f"Merkle root length error: {len(merkle)}"
        
        print(f"✅ Merkle Root: {merkle[:32]}...")
        print(f"✅ Транзакций: {len(txs)}")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

# ============================================================================
# 3. ТЕСТ ТРАНЗАКЦИЙ
# ============================================================================

def test_transaction():
    print("\n" + "=" * 60)
    print("🧪 ТЕСТ 3: ТРАНЗАКЦИИ")
    print("=" * 60)
    
    try:
        from ABSOLUTE_BLOCKCHAIN_FINAL import Transaction
        
        tx = Transaction("alice", "bob", 100.5, fee=0.001)
        
        assert tx.sender == "alice"
        assert tx.receiver == "bob"
        assert tx.amount == 100.5
        assert tx.fee == 0.001
        
        tx_hash = tx.hash()
        assert len(tx_hash) == 64
        
        print(f"✅ Транзакция: {tx.sender} → {tx.receiver}: {tx.amount} ABS")
        print(f"✅ Хеш: {tx_hash[:32]}...")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

# ============================================================================
# 4. ТЕСТ БЛОКА
# ============================================================================

def test_block():
    print("\n" + "=" * 60)
    print("🧪 ТЕСТ 4: БЛОК")
    print("=" * 60)
    
    try:
        from ABSOLUTE_BLOCKCHAIN_FINAL import Block, Transaction
        
        txs = [
            Transaction("alice", "bob", 100),
            Transaction("bob", "charlie", 50),
        ]
        
        block = Block(
            height=1,
            prev_hash="0"*64,
            transactions=txs,
            validator="test_validator",
            difficulty=2
        )
        
        block.block_hash = block.calculate_hash()
        
        assert block.height == 1
        assert len(block.block_hash) == 64
        assert block.block_hash.startswith("00")
        
        print(f"✅ Блок #{block.height}")
        print(f"✅ Хеш: {block.block_hash[:32]}...")
        print(f"✅ Merkle Root: {block.merkle_root()[:32]}...")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

# ============================================================================
# 5. ТЕСТ ВАЛИДАТОРОВ
# ============================================================================

def test_validators():
    print("\n" + "=" * 60)
    print("🧪 ТЕСТ 5: ВАЛИДАТОРЫ")
    print("=" * 60)
    
    try:
        from ABSOLUTE_BLOCKCHAIN_FINAL import ValidatorSet
        
        validators = ValidatorSet()
        validators.register("alice", 100000)
        validators.register("bob", 50000)
        
        stats = validators.get_stats()
        assert stats["total"] == 2
        assert stats["total_stake"] == 150000
        
        validator = validators.select()
        assert validator in ["alice", "bob"]
        
        print(f"✅ Валидаторов: {stats['total']}")
        print(f"✅ Выбран: {validator}")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

# ============================================================================
# 6. ТЕСТ ШАРДИНГА
# ============================================================================

def test_sharding():
    print("\n" + "=" * 60)
    print("🧪 ТЕСТ 6: ШАРДИНГ (64 SHARDS)")
    print("=" * 60)
    
    try:
        from ABSOLUTE_BLOCKCHAIN_FINAL import ShardManager, Transaction
        
        shards = ShardManager(64)
        
        tx1 = Transaction("alice", "bob", 100)
        tx2 = Transaction("bob", "charlie", 50)
        
        shard1 = shards.assign_tx(tx1)
        shard2 = shards.assign_tx(tx2)
        
        assert 0 <= shard1 < 64
        assert 0 <= shard2 < 64
        
        stats = shards.get_stats()
        print(f"✅ Всего шардов: {stats['total']}")
        print(f"✅ Активных шардов: {stats['active']}")
        print(f"✅ Шард tx1: {shard1}, Шард tx2: {shard2}")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

# ============================================================================
# 7. ТЕСТ AI CORE
# ============================================================================

def test_ai_core():
    print("\n" + "=" * 60)
    print("🧪 ТЕСТ 7: AI AUTONOMOUS CORE")
    print("=" * 60)
    
    try:
        from ABSOLUTE_BLOCKCHAIN_FINAL import AIAutonomousCore
        
        ai = AIAutonomousCore()
        
        # Высокая нагрузка
        decision1 = ai.analyze({"mempool": 100, "difficulty": 3})
        assert decision1["action"] == "SCALE_UP"
        
        # Низкая нагрузка
        decision2 = ai.analyze({"mempool": 2, "difficulty": 3})
        assert decision2["action"] == "OPTIMIZE"
        
        # Стабильная
        decision3 = ai.analyze({"mempool": 20, "difficulty": 3})
        assert decision3["action"] == "STABLE"
        
        stats = ai.get_stats()
        print(f"✅ Состояние AI: {stats['state']}")
        print(f"✅ Решений принято: {stats['decisions']}")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

# ============================================================================
# 8. ТЕСТ SELF-HEALING
# ============================================================================

def test_self_healing():
    print("\n" + "=" * 60)
    print("🧪 ТЕСТ 8: SELF-HEALING ENGINE")
    print("=" * 60)
    
    try:
        from ABSOLUTE_BLOCKCHAIN_FINAL import SelfHealingEngine, Block, Transaction
        
        healer = SelfHealingEngine()
        
        # Создаём повреждённую цепочку
        txs = [Transaction("alice", "bob", 100)]
        
        block1 = Block(0, "0"*64, txs, "genesis")
        block1.block_hash = block1.calculate_hash()
        
        block2 = Block(1, "wrong_hash", txs, "validator")
        block2.block_hash = block2.calculate_hash()
        
        chain = [block1, block2]
        
        repaired = healer.repair_chain(chain)
        
        print(f"✅ Восстановлено блоков: {repaired}")
        print(f"✅ Всего восстановлений: {healer.healed}")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

# ============================================================================
# 9. ТЕСТ THREAT DETECTOR
# ============================================================================

def test_threat_detector():
    print("\n" + "=" * 60)
    print("🧪 ТЕСТ 9: AI THREAT DETECTOR")
    print("=" * 60)
    
    try:
        from ABSOLUTE_BLOCKCHAIN_FINAL import AIThreatDetector, Transaction
        
        detector = AIThreatDetector()
        
        # Нормальная транзакция
        tx1 = Transaction("alice", "bob", 100, fee=0.001)
        assert detector.inspect(tx1) == True
        
        # Подозрительная транзакция (большая сумма)
        tx2 = Transaction("alice", "bob", 200000, fee=0.001)
        assert detector.inspect(tx2) == False
        
        # Подозрительная транзакция (маленькая комиссия)
        tx3 = Transaction("alice", "bob", 100, fee=0.00001)
        assert detector.inspect(tx3) == False
        
        stats = detector.get_stats()
        print(f"✅ Блоклист: {stats['blacklist']}")
        print(f"✅ Нормальная TX: одобрена")
        print(f"✅ Подозрительные TX: отклонены")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

# ============================================================================
# 10. ТЕСТ БЛОКЧЕЙН КОРА
# ============================================================================

def test_blockchain_core():
    print("\n" + "=" * 60)
    print("🧪 ТЕСТ 10: BLOCKCHAIN CORE")
    print("=" * 60)
    
    try:
        from ABSOLUTE_BLOCKCHAIN_FINAL import AbsoluteBlockchain, Transaction
        
        bc = AbsoluteBlockchain()
        
        # Добавляем транзакции
        for i in range(10):
            tx = Transaction(f"sender_{i}", f"receiver_{i}", i*10)
            bc.add_transaction(tx)
        
        assert len(bc.mempool) == 10
        
        # Создаём блок
        block = bc.create_block()
        assert block is not None
        
        stats = bc.get_stats()
        assert stats["height"] >= 1
        assert stats["mempool"] <= 10
        
        print(f"✅ Высота: {stats['height']}")
        print(f"✅ Mempool: {stats['mempool']}")
        print(f"✅ Сложность: {stats['difficulty']}")
        print(f"✅ Total Supply: {stats['total_supply']:.2f} ABS")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

# ============================================================================
# 11. ТЕСТ АДАПТИВНЫХ КОМИССИЙ
# ============================================================================

def test_adaptive_fees():
    print("\n" + "=" * 60)
    print("🧪 ТЕСТ 11: ADAPTIVE FEE MARKET")
    print("=" * 60)
    
    try:
        from ABSOLUTE_BLOCKCHAIN_FINAL import AdaptiveFeeMarket
        
        fees = AdaptiveFeeMarket()
        
        fee_low = fees.get_fee(10)
        fee_high = fees.get_fee(2000)
        
        assert fee_high > fee_low
        
        stats = fees.get_stats()
        print(f"✅ Базовая комиссия: {stats['base']}")
        print(f"✅ Текущая комиссия: {stats['current']}")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

# ============================================================================
# 12. ТЕСТ INTEGRATION (ПОЛНЫЙ ЦИКЛ)
# ============================================================================

def test_integration():
    print("\n" + "=" * 60)
    print("🧪 ТЕСТ 12: ПОЛНАЯ ИНТЕГРАЦИЯ")
    print("=" * 60)
    
    try:
        from ABSOLUTE_BLOCKCHAIN_FINAL import AbsoluteBlockchain, Transaction
        
        bc = AbsoluteBlockchain()
        
        # Создаём пользователей
        users = ["alice", "bob", "charlie", "david", "eve"]
        
        # Генерируем транзакции
        for i in range(20):
            sender = users[i % len(users)]
            receiver = users[(i+1) % len(users)]
            amount = (i + 1) * 10
            tx = Transaction(sender, receiver, amount)
            bc.add_transaction(tx)
        
        # Создаём несколько блоков
        blocks_created = 0
        for _ in range(5):
            block = bc.create_block()
            if block:
                blocks_created += 1
        
        stats = bc.get_stats()
        
        print(f"✅ Блоков создано: {blocks_created}")
        print(f"✅ Всего блоков: {stats['height']}")
        print(f"✅ Mempool: {stats['mempool']}")
        print(f"✅ Баланс alice: {bc.get_balance('alice'):.2f} ABS")
        print(f"✅ Баланс bob: {bc.get_balance('bob'):.2f} ABS")
        
        return blocks_created > 0
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

# ============================================================================
# ЗАПУСК ВСЕХ ТЕСТОВ
# ============================================================================

def run_all_tests():
    print("\n" + "=" * 70)
    print("🧪 ЗАПУСК ВСЕХ ТЕСТОВ")
    print("=" * 70)
    
    tests = [
        ("Quantum Hash", test_quantum_hash),
        ("Merkle Tree", test_merkle_root),
        ("Transaction", test_transaction),
        ("Block", test_block),
        ("Validators", test_validators),
        ("Sharding", test_sharding),
        ("AI Core", test_ai_core),
        ("Self-Healing", test_self_healing),
        ("Threat Detector", test_threat_detector),
        ("Blockchain Core", test_blockchain_core),
        ("Adaptive Fees", test_adaptive_fees),
        ("Integration", test_integration),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Тест {name} упал с ошибкой: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 70)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("=" * 70)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ ПРОЙДЕН" if result else "❌ НЕ ПРОЙДЕН"
        print(f"{status}: {name}")
    
    print("-" * 40)
    print(f"ИТОГО: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! БЛОКЧЕЙН РАБОТАЕТ КОРРЕКТНО!")
    else:
        print(f"\n⚠️ НЕ ПРОЙДЕНО ТЕСТОВ: {total - passed}")
    
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
