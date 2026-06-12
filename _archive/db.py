# db.py - SQLite backbone для блокчейна
import sqlite3
import os

DB_PATH = "db/chain.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    cursor = conn.cursor()
    
    # Таблица блоков
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blocks (
            number INTEGER PRIMARY KEY,
            hash TEXT UNIQUE,
            timestamp INTEGER,
            tx_count INTEGER,
            miner TEXT
        )
    ''')
    
    # Таблица транзакций
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            hash TEXT PRIMARY KEY,
            block_number INTEGER,
            from_addr TEXT,
            to_addr TEXT,
            value TEXT,
            timestamp INTEGER,
            FOREIGN KEY (block_number) REFERENCES blocks(number)
        )
    ''')
    
    # Таблица аккаунтов (балансы)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            address TEXT PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            tx_count INTEGER DEFAULT 0
        )
    ''')
    
    # Индексы для быстрого поиска
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tx_from ON transactions(from_addr)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tx_to ON transactions(to_addr)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tx_block ON transactions(block_number)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_blocks_number ON blocks(number)')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")

if __name__ == "__main__":
    init_db()
