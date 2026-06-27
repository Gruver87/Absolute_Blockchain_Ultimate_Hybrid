import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from crypto.keys import KeyGenerator
from crypto.tx_signer import TransactionSigner


def _tx_with_key():
    keypair = KeyGenerator.generate_keypair()
    tx = {
        "from": keypair.address,
        "to": "0x" + "b" * 40,
        "amount": 7,
        "nonce": 1,
        "fee": 0.001,
        "public_key": keypair.public_key.hex(),
    }
    return keypair, tx


def test_transaction_signer_verifies_real_signature():
    keypair, tx = _tx_with_key()
    signature = TransactionSigner.sign_transaction(tx, keypair.private_key.hex())

    assert TransactionSigner.verify_signature(tx, signature, keypair.address) is True


def test_transaction_signer_rejects_tampered_transaction():
    keypair, tx = _tx_with_key()
    signature = TransactionSigner.sign_transaction(tx, keypair.private_key.hex())
    tampered = dict(tx)
    tampered["amount"] = 8

    assert TransactionSigner.verify_signature(tampered, signature, keypair.address) is False


def test_transaction_signer_rejects_fake_signature_and_missing_public_key():
    keypair, tx = _tx_with_key()
    fake_signature = "a" * 64

    assert TransactionSigner.verify_signature(tx, fake_signature, keypair.address) is False

    no_public_key = dict(tx)
    no_public_key.pop("public_key")
    signature = TransactionSigner.sign_transaction(tx, keypair.private_key.hex())
    assert TransactionSigner.verify_signature(no_public_key, signature, keypair.address) is False


def test_transaction_signer_rejects_wrong_address():
    keypair, tx = _tx_with_key()
    signature = TransactionSigner.sign_transaction(tx, keypair.private_key.hex())

    assert TransactionSigner.verify_signature(tx, signature, "0x" + "c" * 40) is False
