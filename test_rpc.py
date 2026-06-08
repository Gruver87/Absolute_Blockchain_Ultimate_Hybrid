import requests
import json

url = "http://localhost:8545"

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

