# core/tx_builder.py
from core.transaction_utxo import UTXOTransaction, TxInput, TxOutput
from crypto.wallet import Wallet

class TransactionBuilder:
    @staticmethod
    def build_transaction(utxo_set, from_addr: str, to_addr: str, amount: float,
                          private_key_hex: str, fee: float = 0.001):
        utxos = utxo_set.get_unspent(from_addr)
        if not utxos:
            raise Exception(f"No UTXO for {from_addr}")
        
        collected = 0.0
        inputs = []
        for utxo in utxos:
            collected += utxo['amount']
            inputs.append(TxInput(tx_hash=utxo['tx_hash'], output_index=utxo['output_index']))
            if collected >= amount + fee:
                break
        
        if collected < amount + fee:
            raise Exception(f"Insufficient balance: {collected} < {amount + fee}")
        
        outputs = [TxOutput(to_addr, amount)]
        change = collected - amount - fee
        if change > 0:
            outputs.append(TxOutput(from_addr, change))
        
        tx = UTXOTransaction(inputs=inputs, outputs=outputs)
        tx.finalize()
        
        for i in range(len(inputs)):
            tx.sign_input(i, private_key_hex)
        
        return tx
    
    @staticmethod
    def create_coinbase_tx(miner: str, amount: float):
        inputs = [TxInput(tx_hash="coinbase", output_index=0)]
        outputs = [TxOutput(miner, amount)]
        tx = UTXOTransaction(inputs=inputs, outputs=outputs)
        tx.finalize()
        return tx
    
    @staticmethod
    def create_genesis_tx(foundation: str, amount: float = 1000000000.0):
        inputs = [TxInput(tx_hash="genesis", output_index=0)]
        outputs = [TxOutput(foundation, amount)]
        tx = UTXOTransaction(inputs=inputs, outputs=outputs)
        tx.finalize()
        return tx
