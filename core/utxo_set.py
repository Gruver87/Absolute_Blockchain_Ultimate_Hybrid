# core/utxo_set.py
import json
from rocksdict import Rdict
from core.utxo import UTXO

class UTXOSet:
    def __init__(self, db_path: str = "data/utxo_db"):
        self.db = Rdict(db_path)
    
    def add_utxo(self, utxo: UTXO):
        key = f"utxo:{utxo.key()}"
        self.db[key] = json.dumps(utxo.to_dict())
    
    def spend_utxo(self, tx_hash: str, output_index: int) -> bool:
        key = f"utxo:{tx_hash}:{output_index}"
        data = self.db.get(key)
        if not data:
            return False
        utxo_data = json.loads(data)
        utxo_data["spent"] = True
        self.db[key] = json.dumps(utxo_data)
        return True
    
    def get_balance(self, address: str) -> float:
        balance = 0.0
        for key, value in self.db.items():
            key_str = key.decode() if isinstance(key, bytes) else key
            if key_str.startswith("utxo:"):
                utxo_data = json.loads(value)
                if utxo_data["owner"] == address and not utxo_data["spent"]:
                    balance += utxo_data["amount"]
        return balance
    
    def get_unspent(self, address: str):
        result = []
        for key, value in self.db.items():
            key_str = key.decode() if isinstance(key, bytes) else key
            if key_str.startswith("utxo:"):
                utxo_data = json.loads(value)
                if utxo_data["owner"] == address and not utxo_data["spent"]:
                    result.append(utxo_data)
        return result
    
    def get_stats(self):
        total = 0
        unspent = 0
        total_amount = 0
        for key, value in self.db.items():
            key_str = key.decode() if isinstance(key, bytes) else key
            if key_str.startswith("utxo:"):
                total += 1
                utxo_data = json.loads(value)
                if not utxo_data["spent"]:
                    unspent += 1
                    total_amount += utxo_data["amount"]
        return {'total_utxos': total, 'unspent_utxos': unspent, 'total_amount': total_amount}
    
    def close(self):
        self.db.close()
