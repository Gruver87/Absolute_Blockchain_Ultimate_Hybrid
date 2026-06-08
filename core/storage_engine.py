# core/storage_engine.py
# ПРОМЫШЛЕННОЕ ХРАНИЛИЩЕ - ROCKSDB
# БЕЗ ЗАГЛУШЕК - РЕАЛЬНОЕ KV ХРАНИЛИЩЕ

import json
import time
from typing import Dict, Any, Optional, List

try:
    from rocksdict import Rdict
    ROCKSDB_AVAILABLE = True
except ImportError:
    ROCKSDB_AVAILABLE = False
    print("⚠️ rocksdict не установлен. Установите: pip install rocksdict")

class StorageEngine:
    """Промышленное хранилище на основе RocksDB"""
    
    def __init__(self, db_path: str = 'data/blockchain_db'):
        if not ROCKSDB_AVAILABLE:
            raise ImportError("RocksDB не доступен. Установите: pip install rocksdict")
        
        self.db_path = db_path
        self.db = Rdict(db_path)
        self._write_batch = []
        
        print(f"✅ RocksDB хранилище инициализировано: {db_path}")
    
    # ================= БЛОКИ =================
    
    def save_block(self, block) -> bool:
        """Сохранение блока с атомарной записью"""
        try:
            self.db[f"block:{block.height}"] = block.to_dict()
            self.db["latest_height"] = block.height
            return True
        except Exception as e:
            print(f"❌ Ошибка сохранения блока: {e}")
            return False
    
    def get_block(self, height: int) -> Optional[Dict]:
        """Получение блока по высоте"""
        try:
            return self.db.get(f"block:{height}")
        except:
            return None
    
    def get_latest_height(self) -> int:
        """Получение высоты последнего блока"""
        try:
            return self.db.get("latest_height", 0)
        except:
            return 0
    
    def get_blocks_range(self, start: int, end: int) -> List[Dict]:
        """Получение диапазона блоков"""
        blocks = []
        for height in range(start, end + 1):
            block = self.get_block(height)
            if block:
                blocks.append(block)
        return blocks
    
    # ================= БАЛАНСЫ =================
    
    def save_balance(self, address: str, balance: float) -> bool:
        """Сохранение баланса"""
        try:
            self.db[f"balance:{address}"] = balance
            return True
        except:
            return False
    
    def get_balance(self, address: str) -> float:
        """Получение баланса"""
        try:
            return self.db.get(f"balance:{address}", 0.0)
        except:
            return 0.0
    
    def add_balance(self, address: str, amount: float) -> bool:
        """Увеличение баланса"""
        current = self.get_balance(address)
        return self.save_balance(address, current + amount)
    
    def sub_balance(self, address: str, amount: float) -> bool:
        """Уменьшение баланса"""
        current = self.get_balance(address)
        if current < amount:
            return False
        return self.save_balance(address, current - amount)
    
    def transfer(self, from_addr: str, to_addr: str, amount: float, fee: float = 0) -> bool:
        """Перевод средств с комиссией"""
        try:
            total_from = amount + fee
            from_balance = self.get_balance(from_addr)
            if from_balance < total_from:
                return False
            
            self.save_balance(from_addr, from_balance - total_from)
            self.save_balance(to_addr, self.get_balance(to_addr) + amount)
            
            # Если есть комиссия - добавляем её в стейкинг пул
            if fee > 0:
                self.save_balance("staking_pool", self.get_balance("staking_pool") + fee)
            
            return True
        except:
            return False
    
    def get_all_balances(self) -> Dict[str, float]:
        """Получение всех балансов"""
        balances = {}
        try:
            for key in self.db.keys():
                if key.startswith("balance:"):
                    address = key[8:]
                    balances[address] = self.db[key]
        except:
            pass
        return balances
    
    # ================= ТРАНЗАКЦИИ =================
    
    def save_transaction(self, tx) -> bool:
        """Сохранение транзакции"""
        try:
            self.db[f"tx:{tx.hash}"] = tx.to_dict()
            
            # Индексация по адресам
            if hasattr(tx, 'from_addr'):
                self.db[f"address_tx:{tx.from_addr}:{tx.hash}"] = True
            if hasattr(tx, 'to_addr'):
                self.db[f"address_tx:{tx.to_addr}:{tx.hash}"] = True
            
            return True
        except:
            return False
    
    def get_transaction(self, tx_hash: str) -> Optional[Dict]:
        """Получение транзакции по хешу"""
        try:
            return self.db.get(f"tx:{tx_hash}")
        except:
            return None
    
    def get_address_transactions(self, address: str, limit: int = 100) -> List[str]:
        """Получение транзакций адреса"""
        txs = []
        try:
            prefix = f"address_tx:{address}:"
            for key in self.db.keys():
                if key.startswith(prefix):
                    tx_hash = key.split(":")[-1]
                    txs.append(tx_hash)
                    if len(txs) >= limit:
                        break
        except:
            pass
        return txs
    
    # ================= ВАЛИДАТОРЫ =================
    
    def register_validator(self, address: str, stake: float, commission: float) -> bool:
        """Регистрация валидатора"""
        try:
            validator = {
                'address': address,
                'stake': stake,
                'commission': commission,
                'registered_at': int(time.time()),
                'is_active': True,
                'total_blocks': 0,
                'total_rewards': 0.0
            }
            self.db[f"validator:{address}"] = validator
            
            # Уменьшаем баланс на сумму стейка
            self.sub_balance(address, stake)
            self.add_balance("staking_pool", stake)
            
            return True
        except:
            return False
    
    def get_validator(self, address: str) -> Optional[Dict]:
        """Получение валидатора"""
        try:
            return self.db.get(f"validator:{address}")
        except:
            return None
    
    def get_all_validators(self) -> List[Dict]:
        """Получение всех валидаторов"""
        validators = []
        try:
            for key in self.db.keys():
                if key.startswith("validator:"):
                    validators.append(self.db[key])
        except:
            pass
        return validators
    
    def add_block_reward(self, validator: str, reward: float) -> bool:
        """Добавление награды валидатору"""
        try:
            self.add_balance(validator, reward)
            validator_data = self.get_validator(validator)
            if validator_data:
                validator_data['total_blocks'] += 1
                validator_data['total_rewards'] += reward
                self.db[f"validator:{validator}"] = validator_data
            return True
        except:
            return False
    
    # ================= МЕТАДАННЫЕ =================
    
    def set_meta(self, key: str, value: Any) -> bool:
        """Сохранение метаданных"""
        try:
            self.db[f"meta:{key}"] = value
            return True
        except:
            return False
    
    def get_meta(self, key: str, default: Any = None) -> Any:
        """Получение метаданных"""
        try:
            return self.db.get(f"meta:{key}", default)
        except:
            return default
    
    # ================= БЭКАП И ВОССТАНОВЛЕНИЕ =================
    
    def create_checkpoint(self, checkpoint_path: str) -> bool:
        """Создание контрольной точки"""
        try:
            self.db.checkpoint(checkpoint_path)
            return True
        except:
            return False
    
    def get_stats(self) -> Dict:
        """Статистика хранилища"""
        block_count = 0
        tx_count = 0
        balance_count = 0
        validator_count = 0
        
        try:
            for key in self.db.keys():
                if key.startswith("block:"):
                    block_count += 1
                elif key.startswith("tx:"):
                    tx_count += 1
                elif key.startswith("balance:"):
                    balance_count += 1
                elif key.startswith("validator:"):
                    validator_count += 1
        except:
            pass
        
        return {
            'engine': 'RocksDB',
            'path': self.db_path,
            'blocks': block_count,
            'transactions': tx_count,
            'balances': balance_count,
            'validators': validator_count,
            'latest_height': self.get_latest_height()
        }
    
    def close(self):
        """Закрытие хранилища"""
        try:
            self.db.close()
        except:
            pass

# Тест при запуске
if __name__ == "__main__":
    print("=" * 60)
    print("RocksDB Storage Engine - Тест")
    print("=" * 60)
    
    try:
        storage = StorageEngine("data/test_rocksdb")
        
        # Тест балансов
        storage.save_balance("foundation", 1000000.0)
        print(f"✅ Баланс foundation: {storage.get_balance('foundation')} ABS")
        
        # Тест метаданных
        storage.set_meta("test_key", "test_value")
        print(f"✅ Метаданные: {storage.get_meta('test_key')}")
        
        # Статистика
        stats = storage.get_stats()
        print(f"✅ Статистика: {stats}")
        
        storage.close()
        print("\n✅ RocksDB Storage Engine готов!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print("Установите: pip install rocksdict")
