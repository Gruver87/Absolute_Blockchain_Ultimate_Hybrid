# -*- coding: utf-8 -*-
"""Helpers for legacy integration scripts."""
import sys

import requests


def skip_if_rpc_down(url: str = "http://localhost:8545", timeout: float = 1.0) -> None:
    try:
        requests.post(
            url,
            json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
            timeout=timeout,
        )
    except Exception:
        print(f"SKIP: RPC node not running at {url}")
        raise SystemExit(0)
