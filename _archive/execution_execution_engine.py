# execution/execution_engine.py
"""
Execution Engine - executes blocks and produces receipts
"""

from typing import List, Dict, Any
from execution.vm import MiniVM
from execution.mempool import Transaction
from execution.receipts import TransactionReceipt, Log, ReceiptStore


class ExecutionEngine:
    """Executes transactions and manages state"""
    
    def __init__(self):
        self.vm = MiniVM()
        self.receipt_store = ReceiptStore()
        self.log_counter = 0
    
    def execute_transaction(self, tx: Transaction, block_number: int = 0,
                           tx_index: int = 0) -> TransactionReceipt:
        """
        Execute a single transaction
        Returns receipt with status and logs
        """
        logs = []
        self.log_counter += 1
        
        try:
            # Reset VM state for this transaction
            self.vm.reset()
            
            # Push transaction value to stack
            self.vm.stack.append(tx.value)
            
            # Execute transaction data as bytecode
            # For simple transfers, just update balance
            if tx.data and len(tx.data) > 0:
                # Execute as contract call (simplified)
                try:
                    # Parse bytecode from data
                    bytecode = []
                    for i in range(0, len(tx.data), 2):
                        if i + 1 < len(tx.data):
                            bytecode.append(("PUSH", tx.data[i]))
                    
                    if bytecode:
                        result = self.vm.execute(bytecode)
                        
                        # Capture logs from VM
                        if hasattr(self.vm, 'logs'):
                            logs.extend(self.vm.logs)
                    
                    status = 1
                    gas_used = self.vm.gas_used
                    
                except Exception as e:
                    status = 0
                    gas_used = tx.gas_limit  # Failed tx still consumes gas
            else:
                # Simple transfer - always succeeds
                status = 1
                gas_used = 21000
            
            # Create receipt
            receipt = TransactionReceipt(
                tx_hash=tx.hash,
                status=status,
                gas_used=min(gas_used, tx.gas_limit),
                gas_price=tx.gas_price,
                logs=logs,
                block_number=block_number,
                transaction_index=tx_index
            )
            
            return receipt
            
        except Exception as e:
            # Transaction failed
            return TransactionReceipt(
                tx_hash=tx.hash,
                status=0,
                gas_used=tx.gas_limit,
                gas_price=tx.gas_price,
                logs=[],
                block_number=block_number,
                transaction_index=tx_index
            )
    
    def execute_block(self, block) -> List[TransactionReceipt]:
        """
        Execute all transactions in a block
        Returns list of receipts
        """
        receipts = []
        
        for i, tx in enumerate(block.transactions):
            receipt = self.execute_transaction(tx, block.number, i)
            self.receipt_store.add_receipt(receipt)
            receipts.append(receipt)
            
            # Remove executed transaction from mempool
            # (mempool.remove_transaction would be called by blockchain)
        
        return receipts
    
    def get_receipt(self, tx_hash: str):
        return self.receipt_store.get_receipt(tx_hash)
    
    def get_logs(self, address: str = None, topic: str = None):
        return self.receipt_store.get_logs(address, topic)
    
    def get_stats(self) -> dict:
        return self.receipt_store.get_stats()
