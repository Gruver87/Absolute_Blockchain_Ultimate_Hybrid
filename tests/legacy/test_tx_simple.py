# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# test_tx_simple.py - Simple transaction test
import requests
import json
import time
from tests.legacy.legacy_helpers import skip_if_rpc_down

url = "http://localhost:8545"
skip_if_rpc_down(url)

print("=" * 60)
print("TESTING TRANSACTIONS")
print("=" * 60)

# Send 3 transactions
for i in range(3):
    tx = {
        "from": "0x40e908721295de4a5cbc775abac8909781aeeea8",
        "to": f"0x{i+1:040x}",
        "value": hex(100 * (i + 1)),
        "gas": "0x5208",
        "gasPrice": hex(i + 1)
    }
    
    payload = {"jsonrpc": "2.0", "method": "eth_sendTransaction", "params": [tx], "id": i+1}
    resp = requests.post(url, json=payload)
    result = resp.json()
    
    if "result" in result:
        print(f"? Tx {i+1}: {result['result'][:20]}...")
    else:
        print(f"? Tx {i+1}: {result}")
    
    time.sleep(0.5)

print("=" * 60)

# Check mempool
payload = {"jsonrpc": "2.0", "method": "eth_getMempoolSize", "params": [], "id": 99}
resp = requests.post(url, json=payload)
result = resp.json()
size = int(result.get("result", "0x0"), 16)
print(f"? Mempool size: {size}")

# Check block number
payload = {"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 100}
resp = requests.post(url, json=payload)
result = resp.json()
block = int(result.get("result", "0x0"), 16)
print(f"? Current block: {block}")

print("=" * 60)
print("? Test complete! Check node window for block creation.")
