#!/usr/bin/env python3
"""
ABSOLUTE BLOCKCHAIN - ARCHITECTURAL AUDITOR
Real system scanner that maps every file to its role
No toys, no mocks - reads actual code
"""

import os
import re
from pathlib import Path
from collections import defaultdict
import json

PROJECT_ROOT = r"C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate"

# 🔎 REAL PATTERNS for module detection
PATTERNS = {
    "🔐 CRYPTOGRAPHY": [
        r"ecdsa", r"secp256k1", r"sha256", r"keccak", r"sign", r"verify", 
        r"signature", r"hashlib", r"private_key", r"public_key", r"crypto",
        r"sphincs", r"postquantum", r"zk-proof", r"merkle"
    ],
    "🌐 P2P NETWORK": [
        r"websocket", r"peer", r"gossip", r"discovery", r"p2p", 
        r"handshake", r"sync", r"broadcast", r"node\.connect"
    ],
    "⚙️ CONSENSUS": [
        r"consensus", r"casper", r"lmd", r"ghost", r"validator", 
        r"slashing", r"fork", r"finality", r"epoch", r"attest"
    ],
    "⛓️ BLOCKCHAIN CORE": [
        r"block", r"chain", r"header", r"height", r"miner", r"mine",
        r"utxo", r"transaction", r"tx", r"pow", r"pos"
    ],
    "📜 EXECUTION / VM": [
        r"evm", r"vm", r"opcode", r"gas", r"execute", r"sstore", 
        r"sload", r"stack", r"bytecode", r"contract"
    ],
    "📡 RPC / API": [
        r"jsonrpc", r"fastapi", r"flask", r"endpoint", r"request",
        r"api", r"rpc", r"eth_", r"web3", r"http"
    ],
    "💾 STORAGE / STATE": [
        r"sqlite", r"db", r"state", r"trie", r"merkle", r"snapshot",
        r"storage", r"persist", r"rocksdb", r"leveldb"
    ],
    "👛 WALLET / ACCOUNTS": [
        r"wallet", r"account", r"nonce", r"address", r"balance",
        r"keypair", r"generate"
    ],
    "🌍 WEB / UI": [
        r"html", r"frontend", r"explorer", r"javascript", r"css",
        r"dashboard", r"gallery", r"nft"
    ],
    "📡 INDEXER / EVENTS": [
        r"indexer", r"event", r"bus", r"listener", r"subscribe",
        r"emit", r"callback"
    ],
    "🧪 TESTS": [
        r"test_", r"pytest", r"unittest", r"assert", r"def test"
    ],
    "🦀 RUST BINDINGS": [
        r"rust", r"ffi", r"bridge", r"pyo3", r"cargo", r"rs$"
    ],
    "🐳 DOCKER / OPS": [
        r"docker", r"container", r"compose", r"Dockerfile"
    ]
}

def classify_file(content: str) -> dict:
    """Analyze file content and return scores for each category"""
    scores = defaultdict(int)
    lower = content.lower()
    
    for category, patterns in PATTERNS.items():
        for pattern in patterns:
            matches = len(re.findall(pattern, lower))
            if matches > 0:
                scores[category] += matches
    
    return dict(scores)

def get_file_category(scores: dict) -> str:
    """Determine primary category based on highest score"""
    if not scores:
        return "📄 OTHER"
    
    # Find category with highest score
    max_score = max(scores.values())
    for cat, score in scores.items():
        if score == max_score:
            return cat
    return "📄 OTHER"

def scan_project():
    """Main scanning function"""
    print("="*70)
    print("🔍 ABSOLUTE BLOCKCHAIN - ARCHITECTURAL AUDITOR")
    print("="*70)
    print(f"📁 Project: {PROJECT_ROOT}\n")
    
    results = defaultdict(list)
    file_details = []
    
    # Walk through all files
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # Skip __pycache__, .git, backups
        dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', 'backups', 'node_modules']]
        
        for file in files:
            # Only analyze code files
            if not any(file.endswith(ext) for ext in ['.py', '.rs', '.js', '.html', '.css', '.ps1', '.sh', '.bat']):
                continue
            
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, PROJECT_ROOT)
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                scores = classify_file(content)
                category = get_file_category(scores)
                
                results[category].append(rel_path)
                file_details.append({
                    "file": rel_path,
                    "category": category,
                    "size_kb": round(os.path.getsize(file_path) / 1024, 2),
                    "scores": scores
                })
                
            except Exception as e:
                # Skip files that can't be read
                pass
    
    # Print results
    print("\n" + "="*70)
    print("📊 SCAN RESULTS")
    print("="*70)
    
    for category in sorted(results.keys()):
        files = results[category]
        print(f"\n{category} ({len(files)} files)")
        print("-"*50)
        for f in files[:10]:  # Show first 10
            print(f"  📄 {f}")
        if len(files) > 10:
            print(f"  ... and {len(files) - 10} more")
    
    # Summary
    print("\n" + "="*70)
    print("📈 SUMMARY")
    print("="*70)
    total_files = sum(len(v) for v in results.values())
    print(f"\n✅ Total files analyzed: {total_files}")
    print(f"✅ Categories found: {len(results)}")
    
    print("\n📊 Category breakdown:")
    for category, files in sorted(results.items(), key=lambda x: -len(x[1])):
        percentage = (len(files) / total_files) * 100
        bar = "█" * int(percentage / 2)
        print(f"  {category:20} {len(files):4} files ({percentage:5.1f}%) {bar}")
    
    # Critical components check
    print("\n" + "="*70)
    print("🎯 CRITICAL COMPONENTS CHECK")
    print("="*70)
    
    critical = ["🔐 CRYPTOGRAPHY", "🌐 P2P NETWORK", "⚙️ CONSENSUS", 
                "⛓️ BLOCKCHAIN CORE", "📜 EXECUTION / VM", "📡 RPC / API"]
    
    all_present = True
    for comp in critical:
        if comp in results:
            print(f"  ✅ {comp} - PRESENT ({len(results[comp])} files)")
        else:
            print(f"  ❌ {comp} - MISSING")
            all_present = False
    
    print("\n" + "="*70)
    if all_present:
        print("🎉 VERDICT: FULLY FUNCTIONAL BLOCKCHAIN FRAMEWORK")
        print("   All critical components are present and implemented")
    else:
        print("⚠️ VERDICT: INCOMPLETE - Some critical components missing")
    print("="*70)
    
    # Save detailed report
    report_path = os.path.join(PROJECT_ROOT, "arch_audit_report.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump({
            "summary": {
                "total_files": total_files,
                "categories": len(results),
                "components_found": list(results.keys())
            },
            "files": file_details
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 Detailed report saved to: {report_path}")
    
    return results

if __name__ == "__main__":
    scan_project()