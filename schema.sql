-- blockchain.db - Mainnet level database schema
-- Таблицы для полноценного блокчейн-эксплорера

-- Блоки
CREATE TABLE IF NOT EXISTS blocks (
    number INTEGER PRIMARY KEY,
    hash TEXT UNIQUE NOT NULL,
    parent_hash TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    tx_count INTEGER DEFAULT 0,
    miner TEXT,
    difficulty TEXT,
    gas_used INTEGER,
    gas_limit INTEGER,
    size INTEGER,
    nonce TEXT,
    indexed_at INTEGER
);

-- Транзакции
CREATE TABLE IF NOT EXISTS transactions (
    hash TEXT PRIMARY KEY,
    block_number INTEGER,
    from_addr TEXT,
    to_addr TEXT,
    value TEXT,
    gas INTEGER,
    gas_price TEXT,
    nonce INTEGER,
    input TEXT,
    timestamp INTEGER,
    status INTEGER DEFAULT 1,
    FOREIGN KEY (block_number) REFERENCES blocks(number)
);

-- Аккаунты (балансы)
CREATE TABLE IF NOT EXISTS accounts (
    address TEXT PRIMARY KEY,
    balance TEXT DEFAULT '0',
    tx_count INTEGER DEFAULT 0,
    first_seen INTEGER,
    last_seen INTEGER
);

-- Токены (ERC20-like)
CREATE TABLE IF NOT EXISTS tokens (
    address TEXT PRIMARY KEY,
    symbol TEXT,
    name TEXT,
    decimals INTEGER DEFAULT 18,
    total_supply TEXT,
    created_at INTEGER
);

-- Трансферы токенов
CREATE TABLE IF NOT EXISTS token_transfers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tx_hash TEXT,
    token_address TEXT,
    sender TEXT,
    receiver TEXT,
    amount TEXT,
    timestamp INTEGER,
    FOREIGN KEY (tx_hash) REFERENCES transactions(hash)
);

-- Mempool (отложенные транзакции)
CREATE TABLE IF NOT EXISTS mempool (
    tx_hash TEXT PRIMARY KEY,
    from_addr TEXT,
    to_addr TEXT,
    value TEXT,
    gas_price TEXT,
    nonce INTEGER,
    added_at INTEGER
);

-- Статистика сети (агрегаты)
CREATE TABLE IF NOT EXISTS network_stats (
    id INTEGER PRIMARY KEY,
    height INTEGER,
    tps REAL,
    avg_block_time REAL,
    total_txs INTEGER,
    total_addresses INTEGER,
    updated_at INTEGER
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_tx_block ON transactions(block_number);
CREATE INDEX IF NOT EXISTS idx_tx_from ON transactions(from_addr);
CREATE INDEX IF NOT EXISTS idx_tx_to ON transactions(to_addr);
CREATE INDEX IF NOT EXISTS idx_tx_timestamp ON transactions(timestamp);
CREATE INDEX IF NOT EXISTS idx_blocks_timestamp ON blocks(timestamp);
CREATE INDEX IF NOT EXISTS idx_token_transfers_token ON token_transfers(token_address);
CREATE INDEX IF NOT EXISTS idx_token_transfers_sender ON token_transfers(sender);
CREATE INDEX IF NOT EXISTS idx_token_transfers_receiver ON token_transfers(receiver);
