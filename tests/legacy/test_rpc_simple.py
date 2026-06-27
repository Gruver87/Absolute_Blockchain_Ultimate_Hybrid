# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# test_rpc_simple.py - Simple RPC test
import requests
import json
from tests.legacy.legacy_helpers import skip_if_rpc_down

url = "http://localhost:8545"
skip_if_rpc_down(url)

methods_to_test = [
    ("eth_blockNumber", []),
    ("eth_chainId", []),
    ("eth_gasPrice", []),
    ("net_version", []),
    ("eth_getMempoolSize", []),
    ("eth_sendTransaction", [{"from": "0x123", "to": "0x456", "value": 100}]),
]

print("=" * 60)
print("RPC METHODS TEST")
print("=" * 60)

for method, params in methods_to_test:
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }
    
    try:
        response = requests.post(url, json=payload, timeout=2)
        result = response.json()
        
        if "result" in result:
            print(f"? {method}: {str(result['result'])[:50]}")
        elif "error" in result:
            print(f"? {method}: {result['error']['message'][:50]}")
        else:
            print(f"?? {method}: Unexpected response")
    except Exception as e:
        print(f"? {method}: {str(e)[:50]}")

print("=" * 60)

# Check if node is alive
try:
    resp = requests.get("http://localhost:8545", timeout=1)
    print(f"Node status: Alive")
except:
    print(f"Node status: Not responding")
print("=" * 60)
