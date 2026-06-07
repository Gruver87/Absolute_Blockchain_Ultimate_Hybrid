# test_rpc_final.py
import requests
import json
import time

url = "http://localhost:8545"

print("=" * 60)
print("RPC METHODS TEST")
print("=" * 60)

# Test 1: eth_blockNumber
print("\n[1] eth_blockNumber:")
payload = {"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}
try:
    resp = requests.post(url, json=payload, timeout=3)
    print(f"    Response: {resp.json()}")
except Exception as e:
    print(f"    Error: {e}")

# Test 2: eth_chainId
print("\n[2] eth_chainId:")
payload = {"jsonrpc": "2.0", "method": "eth_chainId", "params": [], "id": 1}
try:
    resp = requests.post(url, json=payload, timeout=3)
    print(f"    Response: {resp.json()}")
except Exception as e:
    print(f"    Error: {e}")

# Test 3: eth_getMempoolSize
print("\n[3] eth_getMempoolSize:")
payload = {"jsonrpc": "2.0", "method": "eth_getMempoolSize", "params": [], "id": 1}
try:
    resp = requests.post(url, json=payload, timeout=3)
    print(f"    Response: {resp.json()}")
except Exception as e:
    print(f"    Error: {e}")

# Test 4: eth_sendTransaction
print("\n[4] eth_sendTransaction:")
tx = {
    "from": "0x40e908721295de4a5cbc775abac8909781aeeea8",
    "to": "0x3c4d2a58486ff5f3d5b6c8e9a1b2c3d4e5f67890",
    "value": "0x64",
    "gas": "0x5208",
    "gasPrice": "0x1"
}
payload = {"jsonrpc": "2.0", "method": "eth_sendTransaction", "params": [tx], "id": 1}
try:
    resp = requests.post(url, json=payload, timeout=3)
    print(f"    Response: {resp.json()}")
except Exception as e:
    print(f"    Error: {e}")

# Test 5: net_version
print("\n[5] net_version:")
payload = {"jsonrpc": "2.0", "method": "net_version", "params": [], "id": 1}
try:
    resp = requests.post(url, json=payload, timeout=3)
    print(f"    Response: {resp.json()}")
except Exception as e:
    print(f"    Error: {e}")

print("\n" + "=" * 60)
print("✅ Test complete!")
print("=" * 60)
