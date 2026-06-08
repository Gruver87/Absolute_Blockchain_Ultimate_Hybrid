#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""State Manager - управление состояниями аккаунтов"""

import json
import sqlite3
import threading
from typing import Dict, Any, Optional
from contextlib import contextmanager

class StateManager:
    """Управление балансами и состояниями аккаунтов"""
    
    def __init__(self, db_path: str = "data/blockchain.db"):
        self.db_path = db_path
        self.lock = threading.RLock()
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._init_db()
    
    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    
    def _init_db(self):
        """Инициализация таблиц состояния"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS account_state (
                    address TEXT PRIMARY KEY,
                    balance REAL DEFAULT 0,
                    nonce INTEGER DEFAULT 0,
                    last_block INTEGER DEFAULT 0,
                    updated_at INTEGER
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_state_balance ON account_state(balance)')
    
    def get_balance(self, address: str) -> float:
        """Получить баланс адреса"""
        # Проверяем кэш
        if address in self._cache:
            return self._cache[address].get('balance', 0)
        
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT balance FROM account_state WHERE address = ?', (address,))
            row = cursor.fetchone()
            balance = row['balance'] if row else 0
            self._cache[address] = {'balance': balance, 'nonce': 0}
            return balance
    
    def get_nonce(self, address: str) -> int:
        """Получить nonce адреса"""
        if address in self._cache:
            return self._cache[address].get('nonce', 0)
        
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT nonce FROM account_state WHERE address = ?', (address,))
            row = cursor.fetchone()
            nonce = row['nonce'] if row else 0
            if address not in self._cache:
                self._cache[address] = {}
            self._cache[address]['nonce'] = nonce
            return nonce
    
    def update_balance(self, address: str, delta: float) -> bool:
        """Обновить баланс"""
        with self.lock:
            current = self.get_balance(address)
            new_balance = current + delta
            
            if new_balance < 0:
                return False
            
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO account_state 
                    (address, balance, nonce, updated_at)
                    VALUES (?, ?, COALESCE((SELECT nonce FROM account_state WHERE address = ?), 0), ?)
                ''', (address, new_balance, address, int(__import__('time').time())))
            
            # Обновляем кэш
            if address in self._cache:
                self._cache[address]['balance'] = new_balance
            else:
                self._cache[address] = {'balance': new_balance, 'nonce': 0}
            
            return True
    
    def increment_nonce(self, address: str) -> None:
        """Увеличить nonce"""
        with self.lock:
            current = self.get_nonce(address)
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO account_state 
                    (address, balance, nonce, updated_at)
                    VALUES (?, COALESCE((SELECT balance FROM account_state WHERE address = ?), 0), ?, ?)
                ''', (address, address, current + 1, int(__import__('time').time())))
            
            if address in self._cache:
                self._cache[address]['nonce'] = current + 1
    
    def transfer(self, from_addr: str, to_addr: str, amount: float) -> bool:
        """Перевод средств между адресами"""
        with self.lock:
            # Проверяем достаточно ли средств
            balance = self.get_balance(from_addr)
            if balance < amount:
                return False
            
            # Выполняем перевод
            if not self.update_balance(from_addr, -amount):
                return False
            if not self.update_balance(to_addr, amount):
                # Откат
                self.update_balance(from_addr, amount)
                return False
            
            return True
    
    def get_all_balances(self, limit: int = 100) -> Dict[str, float]:
        """Получить все балансы"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT address, balance FROM account_state ORDER BY balance DESC LIMIT ?', (limit,))
            return {row['address']: row['balance'] for row in cursor.fetchall()}
    
    def get_stats(self) -> Dict[str, Any]:
        """Статистика состояния"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) as count, SUM(balance) as total FROM account_state')
            row = cursor.fetchone()
            return {
                'total_accounts': row['count'] or 0,
                'total_balance': row['total'] or 0,
                'cached_accounts': len(self._cache)
            }
    
    def clear_cache(self) -> None:
        """Очистить кэш"""
        self._cache.clear()

# Глобальный экземпляр
state_manager = StateManager()
