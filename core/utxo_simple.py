# core/utxo_simple.py
# UTXO SET - БАЗОВАЯ БЕЗОПАСНОСТЬ ТРАНЗАКЦИЙ

from typing import Dict, List, Optional

class SimpleUTXOSet:
    """Базовый UTXO набор для защиты от double-spend"""
    
    def __init__(self):
        self.utxos: Dict[str, Dict] = {}
        self.spent: Dict[str, bool] = {}
    
    def add_utxo(self, txid: str, output: Dict):
        """Добавление нового UTXO"""
        self.utxos[txid] = output
        self.spent[txid] = False
    
    def add_utxos_from_block(self, block):
        """Добавление всех UTXO из блока"""
        if hasattr(block, 'to_dict'):
            block = block.to_dict()
        
        transactions = block.get('transactions', [])
        for tx in transactions:
            txid = tx.get('tx_hash') or tx.get('hash')
            if txid:
                self.utxos[txid] = {
                    'to': tx.get('to_addr') or tx.get('to'),
                    'amount': tx.get('amount', 0)
                }
                self.spent[txid] = False
    
    def is_spendable(self, txid: str) -> bool:
        """Проверка, можно ли потратить UTXO"""
        return txid in self.utxos and not self.spent.get(txid, True)
    
    def spend(self, txid: str) -> bool:
        """Пометка UTXO как потраченного"""
        if self.is_spendable(txid):
            self.spent[txid] = True
            return True
        return False
    
    def get_balance(self, address: str) -> float:
        """Получение баланса адреса"""
        balance = 0.0
        for txid, utxo in self.utxos.items():
            if not self.spent.get(txid, False):
                if utxo.get('to') == address:
                    balance += utxo.get('amount', 0)
        return balance
    
    def get_stats(self) -> Dict:
        """Статистика UTXO набора"""
        spent_count = 0
        unspent_count = 0
        total_value = 0.0
        
        for txid, utxo in self.utxos.items():
            if self.spent.get(txid, False):
                spent_count += 1
            else:
                unspent_count += 1
                total_value += utxo.get('amount', 0)
        
        return {
            'total_utxos': len(self.utxos),
            'spent': spent_count,
            'unspent': unspent_count,
            'total_value': total_value
        }

# Тест
if __name__ == "__main__":
    utxo = SimpleUTXOSet()
    utxo.add_utxo("tx1", {"to": "alice", "amount": 100})
    print(f"✅ UTXO: {utxo.get_balance('alice')} ABS")
    print(f"   Можем потратить tx1: {utxo.is_spendable('tx1')}")
    utxo.spend("tx1")
    print(f"   После траты: {utxo.is_spendable('tx1')}")
