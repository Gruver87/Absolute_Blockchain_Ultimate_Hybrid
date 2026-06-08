# core/block.py - Compatible Block class
class Block:
    """Block class that works both as dict and object"""
    
    def __init__(self, height, transactions, prev_hash, validator="", timestamp=None):
        self._data = {
            'height': height,
            'transactions': transactions,
            'prev_hash': prev_hash,
            'timestamp': timestamp,
            'validator': validator,
            'nonce': 0,
            'hash': None
        }
    
    def __getitem__(self, key):
        return self._data[key]
    
    def __setitem__(self, key, value):
        self._data[key] = value
    
    @property
    def hash(self):
        return self._data.get('hash')
    
    @hash.setter
    def hash(self, value):
        self._data['hash'] = value
    
    @property
    def height(self):
        return self._data['height']
    
    def to_dict(self):
        return self._data.copy()
