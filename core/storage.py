# core/storage.py
# ABSOLUTE BLOCKCHAIN - LEVELDB STORAGE
# ПОЛНАЯ ЗАМЕНА SQLite НА ПРОМЫШЛЕННОЕ ХРАНИЛИЩЕ

import json
import os
import threading
from typing import Dict, Any, Optional, List

try:
    import plyvel
    LEVELDB_AVAILABLE = True
except ImportError:
    LEVELDB_AVAILABLE = False
    print("⚠️ plyvel не установлен. Установите: pip install plyvel")

class BlockchainStorage:
    """Промышленное хранилище на основе LevelDB"""
    
    def __init__(self, db_path: str = 'data/leveldb'):
        if not LEVELDB_AVAILABLE:
            raise ImportError("LevelDB не доступен. Установите: pip install plyvel")
        
        os.makedirs(db_path, exist_ok=True)
        self.db = plyvel.DB(db_path, create_if_missing=True)
        self.lock = threading.RLock()
        
        print(f"✅ LevelDB инициализирован: {db_path}")
    
    # ========== БЛОКИ ==========
    
    def put_block(self, height: int, block_data: Dict) -> bool:
        """Сохранение блока"""
        try:
            with self.lock:
                key = f"block:{height:010d}".encode()
                value = json.dumps(block_data, default=str, separators=(',', ':')).encode()
                self.db.put(key, value)
                
                # Сохраняем последний блок
                self.db.put(b"latest_block", str(height).encode())
                return True
        except Exception as e:
            print(f"Ошибка сохранения блока {height}: {e}")
            return False
    
    def get_block(self, height: int) -> Optional[Dict]:
        """Получение блока по высоте"""
        with self.lock:
            key = f"block:{height:010d}".encode()
            data = self.db.get(key)
            if data:
                return json.loads(data.decode())
            return None
    
    def get_latest_height(self) -> int:
        """Получение высоты последнего блока"""
        with self.lock:
            data = self.db.get(b"latest_block")
            if data:
                return int(data.decode())
            return -1
    
    def get_blocks_range(self, start_height: int, end_height: int) -> List[Dict]:
        """Получение диапазона блоков"""
        blocks = []
        for height in range(start_height, end_height + 1):
            block = self.get_block(height)
            if block:
                blocks.append(block)
        return blocks
    
    # ========== БАЛАНСЫ ==========
    
    def set_balance(self, address: str, balance: float) -> bool:
        """Установка баланса"""
        with self.lock:
            try:
                key = f"balance:{address}".encode()
                self.db.put(key, str(balance).encode())
                return True
            except:
                return False
    
    def get_balance(self, address: str) -> float:
        """Получение баланса"""
        with self.lock:
            key = f"balance:{address}".encode()
            data = self.db.get(key)
            if data:
                return float(data.decode())
            return 0.0
    
    def add_balance(self, address: str, amount: float) -> bool:
        """Увеличение баланса"""
        current = self.get_balance(address)
        return self.set_balance(address, current + amount)
    
    def sub_balance(self, address: str, amount: float) -> bool:
        """Уменьшение баланса"""
        current = self.get_balance(address)
        if current < amount:
            return False
        return self.set_balance(address, current - amount)
    
    def transfer(self, from_addr: str, to_addr: str, amount: float) -> bool:
        """Перевод средств"""
        with self.lock:
            if not self.sub_balance(from_addr, amount):
                return False
            self.add_balance(to_addr, amount)
            return True
    
    def get_all_balances(self) -> Dict[str, float]:
        """Получение всех балансов"""
        balances = {}
        with self.lock:
            for key, value in self.db:
                if key.startswith(b"balance:"):
                    address = key.decode()[8:]
                    balances[address] = float(value.decode())
        return balances
    
    # ========== ТРАНЗАКЦИИ ==========
    
    def put_transaction(self, tx_hash: str, tx_data: Dict) -> bool:
        """Сохранение транзакции"""
        with self.lock:
            key = f"tx:{tx_hash}".encode()
            value = json.dumps(tx_data, default=str).encode()
            self.db.put(key, value)
            return True
    
    def get_transaction(self, tx_hash: str) -> Optional[Dict]:
        """Получение транзакции"""
        with self.lock:
            key = f"tx:{tx_hash}".encode()
            data = self.db.get(key)
            if data:
                return json.loads(data.decode())
            return None
    
    # ========== ВАЛИДАТОРЫ ==========
    
    def register_validator(self, address: str, stake: float, commission: float) -> bool:
        """Регистрация валидатора"""
        with self.lock:
            validator = {
                'address': address,
                'stake': stake,
                'commission': commission,
                'registered_at': int(__import__('time').time()),
                'is_active': True
            }
            key = f"validator:{address}".encode()
            self.db.put(key, json.dumps(validator).encode())
            return True
    
    def get_validator(self, address: str) -> Optional[Dict]:
        """Получение валидатора"""
        with self.lock:
            key = f"validator:{address}".encode()
            data = self.db.get(key)
            if data:
                return json.loads(data.decode())
            return None
    
    def get_all_validators(self) -> List[Dict]:
        """Получение всех валидаторов"""
        validators = []
        with self.lock:
            for key, value in self.db:
                if key.startswith(b"validator:"):
                    validators.append(json.loads(value.decode()))
        return validators
    
    # ========== СЛУЖЕБНЫЕ ==========
    
    def close(self):
        """Закрытие соединения"""
        with self.lock:
            self.db.close()
    
    def get_stats(self) -> Dict:
        """Статистика хранилища"""
        block_count = 0
        tx_count = 0
        balance_count = 0
        validator_count = 0
        
        with self.lock:
            for key in self.db:
                if key.startswith(b"block:"):
                    block_count += 1
                elif key.startswith(b"tx:"):
                    tx_count += 1
                elif key.startswith(b"balance:"):
                    balance_count += 1
                elif key.startswith(b"validator:"):
                    validator_count += 1
        
        return {
            'blocks': block_count,
            'transactions': tx_count,
            'balances': balance_count,
            'validators': validator_count,
            'latest_height': self.get_latest_height()
        }

# Тест при запуске
if __name__ == "__main__":
    print("=" * 60)
    print("LevelDB Storage - Тест")
    print("=" * 60)
    
    try:
        storage = BlockchainStorage("data/leveldb_test")
        
        # Тест блоков
        storage.put_block(1, {"height": 1, "hash": "test"})
        block = storage.get_block(1)
        print(f"✅ Блок сохранён: {block}")
        
        # Тест балансов
        storage.set_balance("foundation", 1000000.0)
        balance = storage.get_balance("foundation")
        print(f"💰 Баланс foundation: {balance} ABS")
        
        # Тест транзакций
        storage.put_transaction("test_tx", {"hash": "test_tx", "amount": 100})
        print(f"✅ Транзакция сохранена")
        
        # Статистика
        stats = storage.get_stats()
        print(f"📊 Статистика: {stats}")
        
        storage.close()
        print("\n✅ LevelDB Storage готов!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print("Установите: pip install plyvel")
