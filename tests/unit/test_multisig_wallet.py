import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from features.multisig import MultiSigWallet


def test_multisig_rejects_invalid_quorum():
    with pytest.raises(ValueError):
        MultiSigWallet([], 1)
    with pytest.raises(ValueError):
        MultiSigWallet(["0x1", "0x2"], 0)
    with pytest.raises(ValueError):
        MultiSigWallet(["0x1"], 2)


def test_multisig_transaction_requires_real_pending_state():
    wallet = MultiSigWallet(["0x1", "0x2"], 2)

    assert wallet.create_transaction("", 1)["success"] is False
    assert wallet.create_transaction("0x3", 0)["success"] is False

    created = wallet.create_transaction("0x3", 10)
    assert created["success"] is True
    assert created["executed"] is False
    assert wallet.get_transaction(created["tx_id"])["status"] == "pending"


def test_multisig_confirm_requires_owner_and_quorum_without_fake_execution():
    wallet = MultiSigWallet(["0x1", "0x2"], 2)
    tx_id = wallet.create_transaction("0x3", 10)["tx_id"]

    unauthorized = wallet.confirm(tx_id, "0x9")
    assert unauthorized == {"success": False, "error": "owner not authorized"}

    first = wallet.confirm(tx_id, "0x1")
    assert first["success"] is True
    assert first["confirmations"] == 1
    assert first["executed"] is False

    duplicate = wallet.confirm(tx_id, "0x1")
    assert duplicate["success"] is True
    assert duplicate["confirmations"] == 1
    assert duplicate["duplicate"] is True
    assert duplicate["executed"] is False

    second = wallet.confirm(tx_id, "0x2")
    assert second["success"] is True
    assert second["confirmations"] == 2
    assert second["executed"] is False
    assert second["status"] == "approved"
    assert wallet.get_transaction(tx_id)["status"] == "approved"

    already = wallet.confirm(tx_id, "0x2")
    assert already["success"] is True
    assert already["duplicate"] is True


def test_multisig_executes_only_with_transaction_executor():
    calls = []

    def executor(tx):
        calls.append(tx)
        return {"success": True, "tx_hash": "0xabc"}

    wallet = MultiSigWallet(["0x1", "0x2"], 2, transaction_executor=executor)
    tx_id = wallet.create_transaction("0x3", 10)["tx_id"]

    assert wallet.confirm(tx_id, "0x1")["executed"] is False
    second = wallet.confirm(tx_id, "0x2")

    assert second["executed"] is True
    assert second["status"] == "executed"
    assert calls[0]["tx_id"] == tx_id
    stored = wallet.get_transaction(tx_id)
    assert stored["execution_result"]["tx_hash"] == "0xabc"

    already = wallet.confirm(tx_id, "0x2")
    assert already == {"success": False, "error": "transaction already executed"}
