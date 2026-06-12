# send_transaction.py - Send real transactions to the node
import sys
import os
import json
import time
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.wallet_crypto import Wallet
from core.tx_builder import TransactionBuilder

def send_transaction():
    print("=" * 70)
    print("SENDING TRANSACTION TO NODE")
    print("=" * 70)
    
    # Load or create wallets
    print("\n[1] Loading wallets...")
    wallet_a = None
    wallet_b = None
    
    # Try to load existing wallet
    if os.path.exists("data/wallet.json"):
        with open("data/wallet.json", "r") as f:
            wallet_data = json.load(f)
            print(f"   Loaded wallet A: {wallet_data.get('address')[:16]}...")
            # For demo, create a second wallet
            wallet_b = Wallet.create()
            print(f"   Created wallet B: {wallet_b.address[:16]}...")
    else:
        wallet_a = Wallet.create()
        wallet_b = Wallet.create()
        print(f"   Created wallet A: {wallet_a.address[:16]}...")
        print(f"   Created wallet B: {wallet_b.address[:16]}...")
    
    # Create transaction
    print("\n[2] Creating transaction...")
    tx = TransactionBuilder.create_transaction(
        from_addr=wallet_a.address if wallet_a else wallet_data['address'],
        to_addr=wallet_b.address,
        value=100,
        nonce=0,
        gas_price=1,
        gas_limit=21000
    )
    print(f"   From: {tx['from'][:16]}...")
    print(f"   To: {tx['to'][:16]}...")
    print(f"   Value: {tx['value']}")
    
    # Sign transaction
    print("\n[3] Signing transaction...")
    if wallet_a:
        signed_tx = TransactionBuilder.sign_transaction(tx, wallet_a.private_key)
    else:
        # For demo, create a simple signature
        signed_tx = {**tx, 'signature': 'demo_signature', 'hash': 'demo_hash_123'}
    print(f"   Tx hash: {signed_tx.get('hash', 'unknown')}")
    
    # Send via RPC
    print("\n[4] Sending via RPC...")
    url = "http://localhost:8545"
    
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_sendTransaction",
        "params": [signed_tx],
        "id": 1
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        result = response.json()
        print(f"   Response: {result}")
        
        if "result" in result:
            print(f"\n✅ Transaction sent! Hash: {result['result']}")
            
            # Check mempool size
            time.sleep(1)
            mempool_payload = {
                "jsonrpc": "2.0",
                "method": "eth_getMempoolSize",
                "params": [],
                "id": 2
            }
            mempool_response = requests.post(url, json=mempool_payload, timeout=5)
            mempool_result = mempool_response.json()
            print(f"   Mempool size: {int(mempool_result.get('result', 0), 16)}")
            
    except Exception as e:
        print(f"   Error: {e}")
        print("\n⚠️ Make sure node is running on port 8545")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    send_transaction()
