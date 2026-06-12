# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import requests
import json
from tests.legacy.legacy_helpers import skip_if_rpc_down

url = "http://localhost:8545"
skip_if_rpc_down(url)

# Запросы к ноде
calls = [
    ("eth_blockNumber", []),
    ("eth_chainId", []),
    ("eth_getBalance", ["0x40e908721295de4a5cbc775abac8909781aeeea8", "latest"])
]

for method, params in calls:
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }
    try:
        response = requests.post(url, json=payload)
        result = response.json()
        print(f"{method}: {result.get('result', result.get('error'))}")
    except Exception as e:
        print(f"Error: {e}")

