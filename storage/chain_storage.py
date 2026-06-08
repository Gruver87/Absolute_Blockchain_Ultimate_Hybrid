#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chain Storage - постоянное хранение блокчейна с авто-восстановлением"""

import json
import sqlite3
import os
import threading
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

class ChainStorage:
    """Хранение блокчейна в SQLite с поддержкой восстановления"""
    
    def __init__(self, db_path: str = "data/blockchain.db"):
        self.db_path = db_path
        self.lock = threading.RLock()
        
        # Создаём папку data если её нет
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else "data", exist_ok=True)
        
        # Пробуем инициализировать БД
        try:
            self._init_db()
        except (sqlite3.DatabaseError, sqlite3.OperationalError) as e:
            print(f"⚠️ Ошибка БД: {e}. Создаём новую...")
            # Удаляем битый файл
            if os.path.exists(db_path):
                backup_path = db_path + ".backup_" + str(int(__import__('time').time()))
                os.rename(db_path, backup_path)
                print(f"📦 Битый файл сохранён как {backup_path}")
            self._init_db()
    
    @contextmanager
    def _get_conn(self):
        """Получение соединения с БД"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _init_db(self):
        """Инициализация таблиц"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            # Таблица блоков
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS blocks (
                    height INTEGER PRIMARY KEY,
                    block_hash TEXT UNIQUE NOT NULL,
                    previous_hash TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    miner TEXT NOT NULL,
                    transactions TEXT NOT NULL,
                    transaction_count INTEGER DEFAULT 0,
                    total_amount REAL DEFAULT 0,
                    nonce INTEGER DEFAULT 0,
                    merkle_root TEXT NOT NULL
                )
            ''')
            
            # Индексы
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_blocks_hash ON blocks(block_hash)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_blocks_height ON blocks(height)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_blocks_miner ON blocks(miner)')
            
            # Таблица для хранения метаданных
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chain_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at INTEGER
                )
            ''')
    
    def save_block(self, block: Dict[str, Any]) -> bool:
        """Сохранить блок"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO blocks 
                    (height, block_hash, previous_hash, timestamp, miner, transactions, 
                     transaction_count, total_amount, nonce, merkle_root)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    block['height'],
                    block['block_hash'],
                    block['previous_hash'],
                    block['timestamp'],
                    block.get('miner', 'system'),
                    json.dumps(block.get('transactions', [])),
                    len(block.get('transactions', [])),
                    sum(tx.get('amount', 0) for tx in block.get('transactions', [])),
                    block.get('nonce', 0),
                    block.get('merkle_root', '')
                ))
                return True
            except Exception as e:
                print(f"Error saving block: {e}")
                return False
    
    def get_block(self, height: int) -> Optional[Dict[str, Any]]:
        """Получить блок по высоте"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM blocks WHERE height = ?', (height,))
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row)
            return None
    
    def get_last_block(self) -> Optional[Dict[str, Any]]:
        """Получить последний блок"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM blocks ORDER BY height DESC LIMIT 1')
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row)
            return None
    
    def get_all_blocks(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Получить все блоки"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM blocks ORDER BY height ASC LIMIT ?', (limit,))
            return [self._row_to_dict(row) for row in cursor.fetchall()]
    
    def get_blocks_count(self) -> int:
        """Количество блоков в хранилище"""
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM blocks')
                return cursor.fetchone()[0]
        except:
            return 0
    
    def _row_to_dict(self, row) -> Dict[str, Any]:
        """Преобразование строки БД в словарь"""
        data = dict(row)
        if 'transactions' in data and data['transactions']:
            try:
                data['transactions'] = json.loads(data['transactions'])
            except:
                data['transactions'] = []
        else:
            data['transactions'] = []
        return data

# Глобальный экземпляр
try:
    chain_storage = ChainStorage()
    print("✅ Chain Storage: OK")
except Exception as e:
    print(f"⚠️ Chain Storage init: {e}")
    chain_storage = None
