# core/merkle.py
import hashlib
import json

class MerkleTree:
    @staticmethod
    def hash_data(data):
        if isinstance(data, (dict, list)):
            data_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
        else:
            data_str = str(data)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    @classmethod
    def build_merkle_root(cls, transactions):
        if not transactions:
            return hashlib.sha256(b"empty_block").hexdigest()
        
        hashes = [tx.tx_hash for tx in transactions]
        while len(hashes) > 1:
            if len(hashes) % 2 != 0:
                hashes.append(hashes[-1])
            new_hashes = []
            for i in range(0, len(hashes), 2):
                combined = hashes[i] + hashes[i + 1]
                new_hashes.append(cls.hash_data(combined))
            hashes = new_hashes
        return hashes[0]
