# quick_test.py - Simple test for running node
import requests
import json
import time

url = "http://localhost:8545"

print("=" * 50)
print("Quick test for running node")
print("=" * 50)

# 1. Check block number
print("\n[1] Current block:")
payload = {"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}
resp = requests.post(url, json=payload)
print(f"   Block: {resp.json()}")

# 2. Send transaction
print("\n[2] Sending transaction:")
tx = {
    "from": "0x40e908721295de4a5cbc775abac8909781aeeea8",
    "to": "0x9999999999999999999999999999999999999999",
    "value": "0x64",
    "gas": "0x5208",
    "gasPrice": "0x1"
}
payload = {"jsonrpc": "2.0", "method": "eth_sendTransaction", "params": [tx], "id": 2}
resp = requests.post(url, json=payload)
print(f"   Response: {resp.json()}")

# 3. Check mempool
print("\n[3] Mempool size:")
payload = {"jsonrpc": "2.0", "method": "eth_getMempoolSize", "params": [], "id": 3}
resp = requests.post(url, json=payload)
print(f"   Size: {resp.json()}")

# 4. Wait for block
print("\n[4] Waiting 20 seconds for block...")
for i in range(4):
    time.sleep(5)
    payload = {"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 4}
    resp = requests.post(url, json=payload)
    print(f"   Block: {resp.json()}")

print("\n" + "=" * 50)
print("Done!")
