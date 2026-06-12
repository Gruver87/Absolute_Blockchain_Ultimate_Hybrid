# -*- coding: utf-8 -*-
# test_transaction_cycle.py - Full transaction cycle test
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.wallet_crypto import Wallet
from core.tx_builder import TransactionBuilder
from execution.mempool import Mempool
import json

print("=" * 70)
print("FULL TRANSACTION CYCLE TEST")
print("=" * 70)

# 1. Create two wallets
print("\n[1] Creating wallets...")
wallet_a = Wallet.create()
wallet_b = Wallet.create()
print(f"   Wallet A: {wallet_a.address}")
print(f"   Wallet B: {wallet_b.address}")

# 2. Create transaction
print("\n[2] Creating transaction...")
tx = TransactionBuilder.create_transaction(
    from_addr=wallet_a.address,
    to_addr=wallet_b.address,
    value=100,
    nonce=0,
    gas_price=1,
    gas_limit=21000
)
print(f"   Transaction created: {tx}")

# 3. Sign transaction
print("\n[3] Signing transaction...")
signed_tx = TransactionBuilder.sign_transaction(tx, wallet_a.private_key)
print(f"   Signed: {signed_tx.get('hash', 'unknown')}")

# 4. Add to mempool
print("\n[4] Adding to mempool...")
mempool = Mempool()
tx_hash = mempool.add_transaction(signed_tx)
print(f"   Added to mempool: {tx_hash}")
print(f"   Mempool size: {mempool.get_pending_count()}")

# 5. Get transactions for block
print("\n[5] Getting transactions for block...")
pending = mempool.get_transactions_for_block(10)
print(f"   Pending transactions: {len(pending)}")

print("\n" + "=" * 70)
print("? Transaction cycle works!")
print("=" * 70)
print("\nNext steps:")
print("   1. Run: python node_persistent.py")
print("   2. Send transaction via RPC")
print("   3. Check mempool size: curl -X POST http://localhost:8545 -H 'Content-Type: application/json' -d '{\"jsonrpc\":\"2.0\",\"method\":\"eth_getMempoolSize\",\"params\":[],\"id\":1}'")
