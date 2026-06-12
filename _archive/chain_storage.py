#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chain Storage - постоянное хранение блоков"""

import json
import sqlite3
import os
from typing import List, Dict, Optional

class ChainStorage:
    """Хранилище цепочки блоков"""
    
    def __init__(self, db_path: str = "data/chain_storage.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Инициализация БД"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS blocks (
                    height INTEGER PRIMARY KEY,
                    block_hash TEXT UNIQUE NOT NULL,
                    timestamp INTEGER NOT NULL,
                    data TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_hash ON blocks(block_hash)")
    
    def save_block(self, height: int, block_hash: str, timestamp: int, block_data: dict) -> bool:
        """Сохранить блок"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO blocks VALUES (?, ?, ?, ?)",
                    (height, block_hash, timestamp, json.dumps(block_data))
                )
            return True
        except Exception as e:
            print(f"⚠️ Ошибка сохранения блока: {e}")
            return False
    
    def get_block(self, height: int) -> Optional[dict]:
        """Получить блок по высоте"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute("SELECT data FROM blocks WHERE height = ?", (height,)).fetchone()
                return json.loads(row[0]) if row else None
        except Exception as e:
            print(f"⚠️ Ошибка загрузки блока: {e}")
            return None
    
    def get_latest_height(self) -> int:
        """Последняя высота"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute("SELECT MAX(height) FROM blocks").fetchone()
                return row[0] if row and row[0] else -1
        except:
            return -1
    
    def get_all_blocks(self, limit: int = 1000) -> List[dict]:
        """Получить последние блоки"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT data FROM blocks ORDER BY height DESC LIMIT ?",
                    (limit,)
                ).fetchall()
                return [json.loads(row[0]) for row in rows]
        except:
            return []
