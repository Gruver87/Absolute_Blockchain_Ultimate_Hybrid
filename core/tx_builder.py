# -*- coding: utf-8 -*-
"""Legacy transaction builder for integration scripts."""
import time
from typing import Dict

from crypto import native


class TransactionBuilder:
    @staticmethod
    def create_transaction(
        from_addr: str,
        to_addr: str,
        value: float,
        nonce: int = 0,
        gas_price: float = 1.0,
        gas_limit: int = 21000,
        data: str = "",
    ) -> Dict:
        tx = {
            "from": from_addr,
            "to": to_addr,
            "value": value,
            "nonce": nonce,
            "gasPrice": gas_price,
            "gas": gas_limit,
            "data": data,
            "timestamp": int(time.time()),
        }
        raw = f"{from_addr}{to_addr}{value}{nonce}{gas_price}"
        tx["hash"] = "0x" + native.sha256_hex(raw.encode())
        return tx

    @staticmethod
    def sign_transaction(tx: Dict, private_key: str) -> Dict:
        signed = dict(tx)
        signed["signature"] = native.sha256_hex((tx.get("hash", "") + private_key).encode())
        return signed
