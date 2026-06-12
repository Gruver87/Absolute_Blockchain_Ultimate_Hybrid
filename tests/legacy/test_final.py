# test_final.py - Complete transaction test
import requests
import json
import time

url = "http://localhost:8545"

print("=" * 60)
print("FULL TRANSACTION CYCLE TEST")
print("=" * 60)

# Check initial state
print("\n[1] Initial state:")
resp = requests.post(url, json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1})
block_num = resp.json().get("result", "0x0")
print(f"   Block number: {block_num}")

# Send transactions
print("\n[2] Sending transactions...")
txs_sent = 0

for i in range(3):
    tx = {
        "from": "0x40e908721295de4a5cbc775abac8909781aeeea8",
        "to": f"0x{i+1:040x}",
        "value": hex(100 * (i + 1)),
        "gas": "0x5208",
        "gasPrice": hex(i + 1)
    }
    
    payload = {"jsonrpc": "2.0", "method": "eth_sendTransaction", "params": [tx], "id": i+1}
    
    try:
        resp = requests.post(url, json=payload, timeout=3)
        result = resp.json()
        if "result" in result:
            print(f"   ✅ Tx {i+1}: {result['result'][:20]}...")
            txs_sent += 1
        else:
            print(f"   ❌ Tx {i+1}: {result.get('error', {}).get('message', 'Unknown error')}")
    except Exception as e:
        print(f"   ❌ Tx {i+1}: {e}")
    
    time.sleep(0.5)

# Check mempool
print("\n[3] Mempool status:")
payload = {"jsonrpc": "2.0", "method": "eth_getMempoolSize", "params": [], "id": 10}
resp = requests.post(url, json=payload)
result = resp.json()
mempool_size = int(result.get("result", "0x0"), 16)
print(f"   Mempool size: {mempool_size}")

# Wait for mining
if mempool_size > 0:
    print("\n[4] Waiting for blocks (30 seconds)...")
    for i in range(6):
        time.sleep(5)
        resp = requests.post(url, json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 20})
        block_num = resp.json().get("result", "0x0")
        print(f"   Block #{int(block_num, 16)}...", end=" ")
        
        # Check mempool
        resp2 = requests.post(url, json={"jsonrpc": "2.0", "method": "eth_getMempoolSize", "params": [], "id": 21})
        mempool = resp2.json().get("result", "0x0")
        print(f"mempool: {int(mempool, 16)}")
    
    # Final block number
    print("\n[5] Final state:")
    resp = requests.post(url, json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 30})
    final_block = resp.json().get("result", "0x0")
    print(f"   Final block: {final_block}")
    
    if int(final_block, 16) > int(block_num, 16):
        print(f"\n✅ SUCCESS! Blockchain grew from {block_num} to {final_block}")
    else:
        print(f"\n⚠️ Blockchain didn't grow, check node window")
else:
    print("\n⚠️ No transactions in mempool")

print("\n" + "=" * 60)
print("Test complete!")
print("=" * 60)

