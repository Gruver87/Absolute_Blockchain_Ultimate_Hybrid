#!/usr/bin/env python3
"""Compatibility wrapper for the explicit dev/test bridge adapter."""

from bridge.dev_bridge_adapter import (
    BridgeTransaction,
    Chain,
    CrossChainBridge,
    DevBridgeAdapter,
)

def test_bridge():
    print("🌉 Cross-Chain Bridge Test")
    print("=" * 40)
    
    bridge = DevBridgeAdapter()
    
    # Мост между цепочками
    tx = bridge.bridge("ethereum", "absolute", "0xuser_eth", "0xuser_abs", 100)
    print(f"   ✅ Bridge transaction: {tx[:16]}...")
    
    bridge.confirm_transaction(tx)
    
    stats = bridge.get_bridge_stats()
    print(f"   📊 Total transactions: {stats['total_transactions']}")
    print(f"   💰 Total value bridged: {stats['total_value']}")
    print(f"   🔗 Supported chains: {', '.join(stats['supported_chains'])}")
    
    fee = bridge.estimate_fee("ethereum", 100)
    print(f"   💸 Estimated fee: {fee} ETH")
    
    return True

if __name__ == "__main__":
    test_bridge()
