# execution/state_engine.py
"""
State Engine — минимальная машина состояния для блокчейна
- Key-value world state
- Transaction execution
- State checkpoints for rollback
- Simplified state root
"""

import copy
import hashlib
from typing import Dict, Any, Optional


class StateEngine:
    """
    Minimal blockchain state machine
    - state: address -> balance
    - checkpoints for reorg rollback
    - transaction execution
    """

    def __init__(self):
        self.state: Dict[str, int] = {}
        self.checkpoints: Dict[str, Dict[str, int]] = {}  # block_hash -> state snapshot
        self.state_roots: Dict[str, str] = {}  # block_hash -> state root hash
        self.block_state: Dict[str, Dict] = {}  # block_hash -> state after block

    def set_balance(self, address: str, amount: int):
        """Устанавливает баланс адреса"""
        self.state[address] = amount

    def get_balance(self, address: str) -> int:
        """Возвращает баланс адреса"""
        return self.state.get(address, 0)

    def get_state(self) -> Dict[str, int]:
        """Возвращает копию текущего состояния"""
        return copy.deepcopy(self.state)

    def create_checkpoint(self, block_hash: str):
        """Сохраняет состояние перед применением блока (для rollback)"""
        self.checkpoints[block_hash] = copy.deepcopy(self.state)

    def apply_transaction(self, tx: Dict) -> bool:
        """
        Применяет транзакцию
        tx = {from, to, value}
        """
        from_addr = tx.get("from")
        to_addr = tx.get("to")
        value = tx.get("value", 0)

        if from_addr is None or to_addr is None:
            return False

        sender_balance = self.state.get(from_addr, 0)
        if sender_balance < value:
            return False

        self.state[from_addr] = sender_balance - value
        self.state[to_addr] = self.state.get(to_addr, 0) + value

        return True

    def apply_block(self, block: Dict) -> bool:
        """
        Применяет все транзакции блока к состоянию
        """
        block_hash = block.get("hash") or block.get("block_hash")
        if not block_hash:
            return False

        # Сохраняем состояние перед выполнением
        self.create_checkpoint(block_hash)

        # Выполняем транзакции
        for tx in block.get("transactions", []):
            if not self.apply_transaction(tx):
                # Транзакция не прошла — откатываем состояние
                self.rollback(block_hash)
                return False

        # Сохраняем состояние после блока и state root
        self.block_state[block_hash] = copy.deepcopy(self.state)
        self.state_roots[block_hash] = self.compute_state_root()

        return True

    def compute_state_root(self) -> str:
        """
        Вычисляет упрощённый state root (не настоящий Merkle trie)
        Для реального клиента нужен Merkle Patricia Trie
        """
        encoded = str(sorted(self.state.items())).encode()
        return hashlib.sha256(encoded).hexdigest()

    def get_state_root(self, block_hash: str) -> Optional[str]:
        """Возвращает state root для блока"""
        return self.state_roots.get(block_hash)

    def rollback(self, block_hash: str) -> bool:
        """
        Откатывает состояние до checkpoint
        Используется при реорганизации цепочки
        """
        if block_hash in self.checkpoints:
            self.state = copy.deepcopy(self.checkpoints[block_hash])
            return True
        return False

    def rollback_to_checkpoint(self, checkpoint_hash: str) -> bool:
        """Откатывает состояние до указанного checkpoint"""
        return self.rollback(checkpoint_hash)

    def get_stats(self) -> dict:
        return {
            "accounts": len(self.state),
            "total_supply": sum(self.state.values()),
            "checkpoints": len(self.checkpoints),
            "state_roots": len(self.state_roots)
        }

    def clear(self):
        """Очищает всё состояние (для тестов)"""
        self.state.clear()
        self.checkpoints.clear()
        self.state_roots.clear()
        self.block_state.clear()
