#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mempool - пул неподтверждённых транзакций"""

import time
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

@dataclass
class MempoolTransaction:
    """Транзакция в мемпуле"""
    tx_hash: str
    from_addr: str
    to_addr: str
    amount: float
    fee: float
    nonce: int
    timestamp: float
    signature: str = ""
    added_at: float = field(default_factory=time.time)

class Mempool:
    """
    Пул неподтверждённых транзакций
    С поддержкой приоритета по комиссии и nonce
    """
    
    def __init__(self, max_size: int = 10000, min_fee: float = 0.0001):
        self.transactions: Dict[str, MempoolTransaction] = {}
        self.max_size = max_size
        self.min_fee = min_fee
        self.lock = threading.RLock()
    
    def add_transaction(self, tx: MempoolTransaction) -> bool:
        """Добавить транзакцию в мемпул"""
        with self.lock:
            # Проверка на дубликат
            if tx.tx_hash in self.transactions:
                return False
            
            # Проверка минимальной комиссии
            if tx.fee < self.min_fee:
                return False
            
            # Проверка размера
            if len(self.transactions) >= self.max_size:
                # Удаляем самые старые или с низкой комиссией
                self._cleanup()
            
            self.transactions[tx.tx_hash] = tx
            return True
    
    def get_transaction(self, tx_hash: str) -> Optional[MempoolTransaction]:
        """Получить транзакцию по хэшу"""
        with self.lock:
            return self.transactions.get(tx_hash)
    
    def remove_transaction(self, tx_hash: str) -> bool:
        """Удалить транзакцию из мемпула"""
        with self.lock:
            if tx_hash in self.transactions:
                del self.transactions[tx_hash]
                return True
            return False
    
    def get_pending_transactions(self, limit: int = 1000) -> List[MempoolTransaction]:
        """Получить список транзакций для включения в блок"""
        with self.lock:
            # Сортируем по комиссии (выше комиссия - выше приоритет)
            sorted_txs = sorted(
                self.transactions.values(),
                key=lambda tx: tx.fee,
                reverse=True
            )
            return sorted_txs[:limit]
    
    def get_transactions_for_address(self, address: str) -> List[MempoolTransaction]:
        """Получить все транзакции для конкретного адреса"""
        with self.lock:
            return [
                tx for tx in self.transactions.values()
                if tx.from_addr == address or tx.to_addr == address
            ]
    
    def _cleanup(self) -> None:
        """Очистка старых транзакций"""
        now = time.time()
        # Удаляем транзакции старше 1 часа
        to_remove = [
            h for h, tx in self.transactions.items()
            if now - tx.added_at > 3600
        ]
        for h in to_remove:
            del self.transactions[h]
    
    def size(self) -> int:
        """Размер мемпула"""
        with self.lock:
            return len(self.transactions)
    
    def clear(self) -> None:
        """Очистить весь мемпул"""
        with self.lock:
            self.transactions.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Статистика мемпула"""
        with self.lock:
            if not self.transactions:
                return {
                    'size': 0,
                    'avg_fee': 0,
                    'total_amount': 0
                }
            
            total_fee = sum(tx.fee for tx in self.transactions.values())
            total_amount = sum(tx.amount for tx in self.transactions.values())
            
            return {
                'size': len(self.transactions),
                'avg_fee': total_fee / len(self.transactions),
                'total_amount': total_amount
            }
