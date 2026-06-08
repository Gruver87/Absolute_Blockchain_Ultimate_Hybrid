#!/usr/bin/env python3
"""FINAL MIGRATION: добавляем все недостающие колонки и включаем WAL"""

import sqlite3
import os

DB_PATH = "blockchain.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database {DB_PATH} not found")
        return
    
    conn = sqlite3.connect(DB_PATH, timeout=30)
    
    # Включаем WAL
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")
    
    cursor = conn.cursor()
    
    # Получаем существующие колонки
    cursor.execute("PRAGMA table_info(blocks)")
    existing = [col[1] for col in cursor.fetchall()]
    
    print(f"📋 Existing columns: {existing}")
    
    # Добавляем недостающие колонки
    columns_to_add = {
        "indexed_at": "INTEGER",
        "timestamp": "INTEGER",
        "parent_hash": "TEXT"
    }
    
    for col_name, col_type in columns_to_add.items():
        if col_name not in existing:
            try:
                cursor.execute(f"ALTER TABLE blocks ADD COLUMN {col_name} {col_type}")
                print(f"   ✅ Added column: {col_name}")
            except Exception as e:
                print(f"   ⚠️ Could not add {col_name}: {e}")
    
    # Обновляем существующие записи (заполняем indexed_at)
    cursor.execute("UPDATE blocks SET indexed_at = ? WHERE indexed_at IS NULL", (int(__import__('time').time()),))
    print(f"   ✅ Updated indexed_at for existing rows")
    
    conn.commit()
    conn.close()
    
    print("✅ Migration complete! WAL enabled.")

if __name__ == "__main__":
    migrate()
