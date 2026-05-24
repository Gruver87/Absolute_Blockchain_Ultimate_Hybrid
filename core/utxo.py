# core/utxo.py
from dataclasses import dataclass, asdict
import json

@dataclass
class UTXO:
    tx_hash: str
    output_index: int
    owner: str
    amount: float
    spent: bool = False
    
    def key(self) -> str:
        return f"{self.tx_hash}:{self.output_index}"
    
    def to_dict(self):
        return asdict(self)
    
    @staticmethod
    def from_dict(data):
        return UTXO(**data)
