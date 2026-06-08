# blockchain/canonical_serializer.py
# Детерминированная сериализация для консенсуса

import json
from typing import Any, Dict, List, Union

class CanonicalSerializer:
    """Детерминированная JSON сериализация - всегда одинаковый результат"""
    
    @staticmethod
    def serialize(obj: Any) -> str:
        """Сериализует объект в детерминированный JSON"""
        return json.dumps(
            CanonicalSerializer._canonicalize(obj),
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=False
        )
    
    @staticmethod
    def _canonicalize(obj: Any) -> Any:
        """Рекурсивная канонизация объекта"""
        if isinstance(obj, dict):
            return {k: CanonicalSerializer._canonicalize(v) 
                    for k, v in sorted(obj.items())}
        elif isinstance(obj, list):
            return [CanonicalSerializer._canonicalize(item) for item in obj]
        elif isinstance(obj, float):
            # Преобразуем float в int (сатоши)
            return int(obj * 1_000_000)
        else:
            return obj
    
    @staticmethod
    def serialize_block(block: dict) -> str:
        """Сериализация блока для хэширования"""
        canonical_block = {
            'height': block.get('height'),
            'previous_hash': block.get('previous_hash', '0' * 64),
            'timestamp': block.get('timestamp', 0),
            'miner': block.get('miner', ''),
            'nonce': block.get('nonce', 0),
            'transactions': [
                {
                    'hash': tx.get('hash', tx.get('tx_hash', '')),
                    'from': tx.get('from', tx.get('from_addr', '')),
                    'to': tx.get('to', tx.get('to_addr', '')),
                    'amount_satoshi': int(tx.get('amount', 0) * 1_000_000),
                    'fee_satoshi': int(tx.get('fee', 0) * 1_000_000),
                    'nonce': tx.get('nonce', 0),
                    'timestamp': tx.get('timestamp', 0)
                }
                for tx in sorted(block.get('transactions', []), 
                               key=lambda x: x.get('hash', x.get('tx_hash', '')))
            ]
        }
        return CanonicalSerializer.serialize(canonical_block)

canonical_serializer = CanonicalSerializer()
