# test_multi_tx.py - Send multiple transactions to test mempool and blocks
import requests
import json
import time

def get_mempool_size():
    try:
        resp = requests.post("http://localhost:8545", json={
            "jsonrpc": "2.0",
            "method": "eth_getMempoolSize",
            "params": [],
            "id": 1
        }, timeout=2)
        result = resp.json()
        return int(result.get("result", "0x0"), 16)
    except:
        return -1

def get_block_number():
    try:
        resp = requests.post("http://localhost:8545", json={
            "jsonrpc": "2.0",
            "method": "eth_blockNumber",
            "params": [],
            "id": 1
        }, timeout=2)
        result = resp.json()
        return int(result.get("result", "0x0"), 16)
    except:
        return -1

print("=" * 70)
print("MONITORING NODE STATUS")
print("=" * 70)

while True:
    block_num = get_block_number()
    mempool_size = get_mempool_size()
    
    print(f"\r📊 Block: {block_num} | Mempool: {mempool_size} txs", end="")
    
    if mempool_size > 0:
        print(f" 🔥", end="")
    
    time.sleep(3)
