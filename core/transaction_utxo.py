# core/transaction_utxo.py
import hashlib
import json
import time
from dataclasses import dataclass, field
from crypto.wallet import Wallet

@dataclass
class TxInput:
    tx_hash: str
    output_index: int
    signature: str = ""
    public_key: str = ""
    
    def to_dict(self):
        return {'tx_hash': self.tx_hash, 'output_index': self.output_index, 
                'signature': self.signature, 'public_key': self.public_key}
    
    @staticmethod
    def from_dict(data):
        return TxInput(data['tx_hash'], data['output_index'], 
                       data.get('signature', ''), data.get('public_key', ''))

@dataclass
class TxOutput:
    address: str
    amount: float
    
    def to_dict(self):
        return {'address': self.address, 'amount': self.amount}
    
    @staticmethod
    def from_dict(data):
        return TxOutput(data['address'], data['amount'])

@dataclass
class UTXOTransaction:
    inputs: list
    outputs: list
    timestamp: int = field(default_factory=lambda: int(time.time()))
    tx_hash: str = ""
    
    def calculate_hash(self):
        data = {
            "inputs": [i.to_dict() for i in self.inputs],
            "outputs": [o.to_dict() for o in self.outputs],
            "timestamp": self.timestamp
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    
    def finalize(self):
        self.tx_hash = self.calculate_hash()
    
    def sign_input(self, input_index: int, private_key_hex: str):
        if input_index >= len(self.inputs):
            return
        signature, public_key = Wallet.sign_message(private_key_hex, self.tx_hash)
        self.inputs[input_index].signature = signature
        self.inputs[input_index].public_key = public_key
    
    def verify(self):
        for tx_input in self.inputs:
            if not Wallet.verify_signature(tx_input.public_key, self.tx_hash, tx_input.signature):
                return False
        return True
    
    def to_dict(self):
        return {
            'tx_hash': self.tx_hash,
            'inputs': [i.to_dict() for i in self.inputs],
            'outputs': [o.to_dict() for o in self.outputs],
            'timestamp': self.timestamp
        }
    
    @staticmethod
    def from_dict(data):
        inputs = [TxInput.from_dict(i) for i in data['inputs']]
        outputs = [TxOutput.from_dict(o) for o in data['outputs']]
        return UTXOTransaction(inputs, outputs, data.get('timestamp', int(time.time())), data.get('tx_hash', ''))
