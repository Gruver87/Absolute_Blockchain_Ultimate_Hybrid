# send_transaction_simple.py - Simple transaction sender
import requests
import json
import time

def send_test_transaction():
    url = "http://localhost:8545"
    
    print("=" * 60)
    print("SENDING TEST TRANSACTION")
    print("=" * 60)
    
    # Simple transaction object
    tx = {
        "from": "0x40e908721295de4a5cbc775abac8909781aeeea8",
        "to": "0x3c4d2a58486ff5f3d5b6c8e9a1b2c3d4e5f67890",
        "value": "0x64",  # 100 in hex
        "gas": "0x5208",  # 21000
        "gasPrice": "0x1"
    }
    
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_sendTransaction",
        "params": [tx],
        "id": 1
    }
    
    print(f"Sending: {tx['value']} from {tx['from'][:16]}... to {tx['to'][:16]}...")
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        
        if "result" in result:
            print(f"\n✅ Transaction sent! Hash: {result['result']}")
        else:
            print(f"\n⚠️ Transaction failed: {result.get('error', {}).get('message', 'Unknown error')}")
            
    except Exception as e:
        print(f"Error: {e}")
    
    print("=" * 60)

if __name__ == "__main__":
    send_test_transaction()
