# consensus/heaviest_chain.py
# HEAVIEST CHAIN RULE - ВЫБОР ЦЕПОЧКИ ПО РАБОТЕ

from typing import List, Dict

class Consensus:
    """Консенсус на основе веса цепочки (work-based)"""
    
    def __init__(self, blockchain):
        self.bc = blockchain
    
    def chain_weight(self, chain: List) -> int:
        """Вычисление суммарного веса цепочки"""
        weight = 0
        for block in chain:
            if hasattr(block, 'difficulty'):
                difficulty = block.difficulty
            else:
                difficulty = block.get('difficulty', 1)
            weight += difficulty
        return weight
    
    def try_replace_chain(self, new_chain: List) -> bool:
        """
        Замена цепочки если новая тяжелее
        Возвращает True если цепочка заменена
        """
        current_weight = self.chain_weight(self.bc.chain)
        new_weight = self.chain_weight(new_chain)
        
        if new_weight > current_weight:
            self.bc.chain = new_chain
            print(f"🔄 Chain reorg! Вес: {current_weight} → {new_weight}")
            return True
        
        return False
    
    def get_best_chain(self, chains: List[List]) -> List:
        """Выбор лучшей цепочки из нескольких"""
        best_chain = None
        best_weight = 0
        
        for chain in chains:
            weight = self.chain_weight(chain)
            if weight > best_weight:
                best_chain = chain
                best_weight = weight
        
        return best_chain
    
    def is_heavier(self, chain_a: List, chain_b: List) -> bool:
        """Сравнение веса двух цепочек"""
        return self.chain_weight(chain_a) > self.chain_weight(chain_b)

# Тест
if __name__ == "__main__":
    print("✅ Consensus готов")
