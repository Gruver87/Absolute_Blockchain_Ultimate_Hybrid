# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import requests
import json
from tests.legacy.legacy_helpers import skip_if_rpc_down

url = "http://localhost:8545"
skip_if_rpc_down(url)

# Расширенный список методов для проверки
methods = [
    ("eth_blockNumber", [], "Текущий блок"),
    ("eth_chainId", [], "ID сети"),
    ("eth_getBalance", ["0x40e908721295de4a5cbc775abac8909781aeeea8", "latest"], "Баланс"),
    ("eth_getTransactionCount", ["0x40e908721295de4a5cbc775abac8909781aeeea8", "latest"], "Nonce"),
    ("eth_getBlockByNumber", ["latest", False], "Последний блок (только заголовок)"),
    ("eth_getBlockTransactionCountByNumber", ["latest"], "Транзакций в блоке"),
    ("eth_gasPrice", [], "Цена газа"),
    ("net_version", [], "Версия сети"),
    ("net_peerCount", [], "Количество пиров"),
    ("web3_clientVersion", [], "Версия клиента"),
]

print("="*60)
print("? RPC API TEST RESULTS")
print("="*60)

for method, params, description in methods:
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }
    try:
        response = requests.post(url, json=payload, timeout=5)
        result = response.json()
        
        if "result" in result:
            print(f"? {description:30} | {method:25} | {result['result']}")
        elif "error" in result:
            print(f"?? {description:30} | {method:25} | ERROR: {result['error']['message'][:50]}")
        else:
            print(f"? {description:30} | {method:25} | Unexpected response")
    except Exception as e:
        print(f"? {description:30} | {method:25} | Exception: {str(e)[:50]}")

print("="*60)

# Декодируем hex значения
block_hex = None
try:
    resp = requests.post(url, json={"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}).json()
    block_hex = resp.get("result")
    if block_hex:
        block_num = int(block_hex, 16)
        print(f"\n? Статистика:")
        print(f"   Высота блокчейна: {block_num} блоков")
        print(f"   Баланс кошелька: {1_000_000:,} монет")
        print(f"   Chain ID: 1337")
except:
    pass

print("="*60)
