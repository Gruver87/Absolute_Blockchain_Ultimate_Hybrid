# storage/rocksdb_storage.py
from rocksdict import Rdict
import json

class RocksDBStorage:
    def __init__(self, path: str = "data/blockchain"):
        self.db = Rdict(path)
    
    def save_block(self, block):
        self.db[f"block:{block.height}"] = json.dumps(block.to_dict())
        self.db["chain:latest_height"] = str(block.height)
    
    def get_block(self, height: int):
        data = self.db.get(f"block:{height}")
        return json.loads(data) if data else None
    
    def get_chain_height(self):
        h = self.db.get("chain:latest_height")
        return int(h) if h else 0
    
    def close(self):
        self.db.close()
