#!/usr/bin/env python3
"""Migration: add indexed_at column to blocks table"""

import sqlite3
import os

DB_PATH = "blockchain.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database {DB_PATH} not found")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Проверяем существующие колонки
    cursor.execute("PRAGMA table_info(blocks)")
    columns = [col[1] for col in cursor.fetchall()]
    
    print(f"📋 Existing columns: {columns}")
    
    # Добавляем indexed_at если нет
    if "indexed_at" not in columns:
        cursor.execute("ALTER TABLE blocks ADD COLUMN indexed_at INTEGER")
        print("✅ Added column: indexed_at")
    else:
        print("✅ Column indexed_at already exists")
    
    # Добавляем timestamp если нет
    if "timestamp" not in columns:
        cursor.execute("ALTER TABLE blocks ADD COLUMN timestamp INTEGER")
        print("✅ Added column: timestamp")
    else:
        print("✅ Column timestamp already exists")
    
    # Добавляем parent_hash если нет
    if "parent_hash" not in columns:
        cursor.execute("ALTER TABLE blocks ADD COLUMN parent_hash TEXT")
        print("✅ Added column: parent_hash")
    else:
        print("✅ Column parent_hash already exists")
    
    conn.commit()
    conn.close()
    
    print("✅ Migration complete!")

if __name__ == "__main__":
    migrate()
