#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FORK CHOICE SIMULATOR - GHOST / LMD-GHOST алгоритмы"""

import json
import time
from typing import List, Dict, Any
from collections import defaultdict

class Block:
    def __init__(self, number: int, parent_hash: str, validator: str):
        self.number = number
        self.parent_hash = parent_hash
        self.validator = validator
        self.hash = hashlib.sha256(f"{number}{parent_hash}{validator}{time.time()}".encode()).hexdigest()[:16]
        self.children: List[Block] = []
        self.weight = 1
        self.votes = 0

class ForkChoice:
    """GHOST / LMD-GHOST fork choice rule"""
    
    def __init__(self):
        self.blocks: Dict[str, Block] = {}
        self.genesis = Block(0, "0"*16, "genesis")
        self.blocks[self.genesis.hash] = self.genesis
    
    def add_block(self, number: int, parent_hash: str, validator: str) -> str:
        """Добавление блока в дерево"""
        block = Block(number, parent_hash, validator)
        self.blocks[block.hash] = block
        
        if parent_hash in self.blocks:
            self.blocks[parent_hash].children.append(block)
        
        return block.hash
    
    def compute_weight(self, block: Block) -> int:
        """Вычисление веса поддерева (GHOST)"""
        weight = block.weight
        for child in block.children:
            weight += self.compute_weight(child)
        return weight
    
    def get_head_ghost(self, root: Block) -> Block:
        """GHOST алгоритм выбора головы"""
        current = root
        
        while current.children:
            # Находим ребёнка с максимальным весом
            best_child = max(current.children, key=lambda c: self.compute_weight(c))
            current = best_child
        
        return current
    
    def add_vote(self, block_hash: str):
        """Добавление голоса за блок (LMD-GHOST)"""
        if block_hash in self.blocks:
            self.blocks[block_hash].votes += 1
    
    def get_head_lmd_ghost(self) -> Block:
        """LMD-GHOST - учитывает голоса валидаторов"""
        current = self.genesis
        
        while current.children:
            # Выбираем ребёнка с максимальным количеством голосов
            best_child = max(current.children, key=lambda c: c.votes)
            current = best_child
        
        return current
    
    def print_tree(self, block: Block, depth: int = 0):
        """Печать дерева форков"""
        indent = "  " * depth
        print(f"{indent}🔷 Block #{block.number} ({block.hash[:8]}) - votes: {block.votes}")
        for child in block.children:
            self.print_tree(child, depth + 1)
    
    def detect_forks(self) -> List[Dict]:
        """Обнаружение форков (несколько детей)"""
        forks = []
        for block in self.blocks.values():
            if len(block.children) > 1:
                forks.append({
                    "block": block.number,
                    "hash": block.hash,
                    "children": [c.number for c in block.children],
                    "depth": max(len(str(c.number)) for c in block.children)
                })
        return forks

def test_fork_choice():
    print("🌲 Fork Choice Simulator")
    print("=" * 40)
    
    fc = ForkChoice()
    
    # Создаём цепочку
    b1 = fc.add_block(1, fc.genesis.hash, "val1")
    b2 = fc.add_block(2, b1, "val2")
    b3 = fc.add_block(3, b2, "val3")
    
    # Создаём форк
    b2_alt = fc.add_block(2, b1, "val4")
    b3_alt = fc.add_block(3, b2_alt, "val5")
    
    # Добавляем голоса
    fc.add_vote(b3)
    fc.add_vote(b3)
    fc.add_vote(b3_alt)
    
    print("📊 Блокчейн дерево:")
    fc.print_tree(fc.genesis)
    
    head_ghost = fc.get_head_ghost(fc.genesis)
    print(f"\n🎯 GHOST head: Block #{head_ghost.number}")
    
    head_lmd = fc.get_head_lmd_ghost()
    print(f"🎯 LMD-GHOST head: Block #{head_lmd.number}")
    
    forks = fc.detect_forks()
    print(f"\n🔀 Forks detected: {len(forks)}")
    for fork in forks:
        print(f"   Block #{fork['block']} → {fork['children']}")
    
    return True

if __name__ == "__main__":
    import hashlib
    test_fork_choice()
