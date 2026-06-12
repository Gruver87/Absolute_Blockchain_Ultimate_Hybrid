#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
"""Tests for Slashing Engine"""

import sys
from consensus.slashing import SlashingEngine

def test_slashing():
    passed = 0
    failed = 0
    
    print("\nTesting Slashing Engine...")
    
    # Test 1: Double vote
    engine = SlashingEngine()
    engine.add_vote("val1", 10, "block_A")
    result = engine.add_vote("val1", 10, "block_B")
    assert result == False, "Should reject double vote"
    assert engine.is_slashed("val1"), "Should be slashed"
    passed += 1
    print("? Double vote test passed")
    
    # Test 2: Double proposal
    engine = SlashingEngine()
    engine.add_proposal("val2", 100, "block_X")
    result = engine.add_proposal("val2", 100, "block_Y")
    assert engine.is_slashed("val2"), "Should slash double proposer"
    passed += 1
    print("? Double proposal test passed")
    
    # Test 3: Invalid proposal
    engine = SlashingEngine()
    engine.report_invalid_proposal("val3", 200, "bad state")
    assert engine.is_slashed("val3"), "Should slash invalid proposal"
    passed += 1
    print("? Invalid proposal test passed")
    
    # Test 4: Summary
    engine = SlashingEngine()
    engine.add_vote("val4", 10, "block_A")
    engine.add_vote("val4", 10, "block_B")
    summary = engine.get_summary()
    assert summary["total_slashed"] == 1, "Summary should show 1 slashed"
    passed += 1
    print("? Summary test passed")
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0

if __name__ == "__main__":
    success = test_slashing()
    sys.exit(0 if success else 1)
