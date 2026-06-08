-- Final schema - НЕ МЕНЯТЬ!
CREATE TABLE IF NOT EXISTS blocks (
    number INTEGER PRIMARY KEY,
    hash TEXT,
    parent_hash TEXT,
    timestamp INTEGER,
    miner TEXT,
    tx_count INTEGER
);

CREATE TABLE IF NOT EXISTS transactions (
    hash TEXT PRIMARY KEY,
    block_number INTEGER,
    from_addr TEXT,
    to_addr TEXT,
    value TEXT,
    gas INTEGER,
    timestamp INTEGER
);

CREATE TABLE IF NOT EXISTS addresses (
    address TEXT PRIMARY KEY,
    balance TEXT DEFAULT '0',
    tx_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_blocks_number ON blocks(number);
CREATE INDEX IF NOT EXISTS idx_tx_block ON transactions(block_number);
CREATE INDEX IF NOT EXISTS idx_tx_from ON transactions(from_addr);
CREATE INDEX IF NOT EXISTS idx_tx_to ON transactions(to_addr);
