# diagnose.py - Direct mempool and mining test
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from execution.mempool import Mempool
from core.blockchain import Blockchain
from core.wallet_crypto import Wallet
import time
import hashlib

print("=" * 60)
print("DIAGNOSTIC TEST")
print("=" * 60)

# 1. Create mempool and add transactions
print("\n[1] Creating mempool and adding transactions...")
mempool = Mempool()
wallet = Wallet.create()

txs = []
for i in range(3):
    tx = {
        "from": "0x40e908721295de4a5cbc775abac8909781aeeea8",
        "to": f"0x{i+1:040x}",
        "value": hex(100 * (i + 1)),
        "gas": "0x5208",
        "gasPrice": hex(i + 1)
    }
    tx_hash = mempool.add_transaction(tx)
    txs.append(tx)
    print(f"   Added tx {i+1}: {tx_hash[:16]}...")

print(f"\n[2] Mempool size: {mempool.get_pending_count()}")

# 2. Check get_sorted_transactions
print("\n[3] Testing get_sorted_transactions...")
sorted_txs = mempool.get_sorted_transactions(100)
print(f"   Returned {len(sorted_txs)} transactions")

# 3. Check direct access to transactions dict
print("\n[4] Checking internal transactions dict...")
if hasattr(mempool, 'transactions'):
    print(f"   transactions dict has {len(mempool.transactions)} items")
    for key, value in list(mempool.transactions.items())[:3]:
        print(f"      {key[:16]}... -> {value.get('to', '')[:16]}...")

# 4. Create blockchain and mine a block
print("\n[5] Creating blockchain and mining block...")
blockchain = Blockchain()
if blockchain.get_height() == 0:
    genesis = blockchain.create_genesis_block()
    blockchain.add_block(genesis)
    print("   Genesis created")

# Mine block with transactions
height = blockchain.get_height()
prev_hash = '0'*16
if height > 0:
    last = blockchain.get_latest_block()
    prev_hash = last.get('hash', '0'*16)

# Get transactions from mempool
transactions = mempool.get_sorted_transactions(100)
print(f"   Got {len(transactions)} transactions from mempool")

block = {
    'height': height,
    'transactions': transactions,
    'prev_hash': prev_hash,
    'timestamp': time.time(),
    'validator': wallet.address,
    'nonce': 0,
    'hash': None
}

block_string = f"{block['height']}{block['transactions']}{block['prev_hash']}{block['timestamp']}{block['validator']}"
block['hash'] = hashlib.sha256(block_string.encode()).hexdigest()[:16]

if blockchain.add_block(block):
    print(f"   ✅ Block #{block['height']} added with {len(transactions)} transactions")
    print(f"   Block hash: {block['hash']}")
    
    # Check if transactions were removed from mempool
    if transactions:
        tx_hashes = [tx.get('hash', '') for tx in transactions if tx.get('hash')]
        mempool.remove_transactions(tx_hashes)
        print(f"   Removed {len(tx_hashes)} transactions from mempool")
        print(f"   Mempool size after: {mempool.get_pending_count()}")
else:
    print("   ❌ Failed to add block")

print("\n" + "=" * 60)
print("Diagnostic complete!")
print("=" * 60)
