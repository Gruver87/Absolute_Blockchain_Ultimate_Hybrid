# execution/receipts.py
"""
Transaction receipts with logs and events
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Log:
    """Event log from transaction"""
    address: str
    topics: List[str]
    data: bytes
    block_number: int
    tx_hash: str
    log_index: int


@dataclass
class TransactionReceipt:
    """Receipt for executed transaction"""
    tx_hash: str
    status: int  # 1 = success, 0 = failure
    gas_used: int
    gas_price: int
    logs: List[Log]
    contract_address: Optional[str] = None
    block_number: int = 0
    block_hash: str = ""
    transaction_index: int = 0
    
    def to_dict(self) -> dict:
        return {
            "tx_hash": self.tx_hash,
            "status": self.status,
            "gas_used": self.gas_used,
            "gas_price": self.gas_price,
            "logs": [
                {
                    "address": log.address,
                    "topics": log.topics,
                    "data": log.data.hex() if isinstance(log.data, bytes) else log.data,
                    "block_number": log.block_number,
                    "tx_hash": log.tx_hash,
                    "log_index": log.log_index
                }
                for log in self.logs
            ],
            "contract_address": self.contract_address,
            "block_number": self.block_number
        }


class ReceiptStore:
    """Store and query transaction receipts"""
    
    def __init__(self):
        self.receipts: Dict[str, TransactionReceipt] = {}
        self.logs: List[Log] = []
    
    def add_receipt(self, receipt: TransactionReceipt):
        self.receipts[receipt.tx_hash] = receipt
        for log in receipt.logs:
            self.logs.append(log)
    
    def get_receipt(self, tx_hash: str) -> Optional[TransactionReceipt]:
        return self.receipts.get(tx_hash)
    
    def get_logs(self, address: str = None, topic: str = None) -> List[Log]:
        logs = self.logs
        if address:
            logs = [log for log in logs if log.address == address]
        if topic:
            logs = [log for log in logs if topic in log.topics]
        return logs
    
    def get_stats(self) -> dict:
        success_count = sum(1 for r in self.receipts.values() if r.status == 1)
        return {
            "total_receipts": len(self.receipts),
            "successful_txs": success_count,
            "failed_txs": len(self.receipts) - success_count,
            "total_logs": len(self.logs)
        }
