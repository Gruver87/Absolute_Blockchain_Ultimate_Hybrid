#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Генерация RPC API key для .env (не коммитить ключ в git)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from middleware.rpc_auth import RPCApiKeyAuth

if __name__ == "__main__":
    key = RPCApiKeyAuth.generate_key()
    print("Add to your local .env (never commit):")
    print(f"RPC_API_KEY_REQUIRED=true")
    print(f"RPC_API_KEYS={key}")
    print()
    print("Usage:")
    print(f'curl -H "X-API-Key: {key}" -X POST http://localhost:8545 ...')
