#!/usr/bin/env python3
"""
RUNTIME TRUTH AUDITOR - Реальный анализ работающих компонентов
Анализирует импорты от точки входа до самого низа
"""

import ast
import sys
import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(r"C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate")

# Выберите ТОЛЬКО ОДНУ точку входа для анализа
ENTRY_POINTS = {
    "main": "main.py",                    # Новая архитектура
    # "run_unified": "run_unified.py",    # Unified версия
    # "node_persistent": "node_persistent.py",  # Старая версия
}

def find_module_file(module_name: str, root: Path) -> Path | None:
    """Находит файл по имени модуля"""
    # Прямой файл
    direct = root / f"{module_name}.py"
    if direct.exists():
        return direct
    
    # В папках
    for py in root.rglob("*.py"):
        if py.stem == module_name and "__pycache__" not in str(py):
            return py
    
    # Как пакет
    pkg = root / module_name / "__init__.py"
    if pkg.exists():
        return pkg
    
    return None

def get_imports_from_file(file_path: Path) -> list:
    """Извлекает имена импортируемых модулей"""
    imports = []
    try:
        source = file_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module and not node.module.startswith('.'):
                    imports.append(node.module.split('.')[0])
    except:
        pass
    return list(set(imports))

def build_dependency_tree(entry_file: Path, root: Path, max_depth: int = 10):
    """Строит дерево зависимостей"""
    visited = set()
    dependencies = {}
    import_graph = defaultdict(set)
    reverse_graph = defaultdict(set)
    
    def traverse(file_path: Path, depth: int = 0):
        if depth > max_depth:
            return
        if file_path in visited:
            return
        visited.add(file_path)
        
        rel_path = file_path.relative_to(root)
        module_name = file_path.stem
        
        imports = get_imports_from_file(file_path)
        
        for imp in imports:
            dep_file = find_module_file(imp, root)
            if dep_file and dep_file != file_path:
                import_graph[rel_path].add(dep_file.relative_to(root))
                reverse_graph[dep_file.relative_to(root)].add(rel_path)
                traverse(dep_file, depth + 1)
    
    traverse(entry_file)
    return import_graph, reverse_graph, visited

def classify_component(module_path: str) -> str:
    """Классифицирует модуль по компоненту"""
    path_lower = module_path.lower()
    if "crypto" in path_lower or "wallet" in path_lower or "sign" in path_lower:
        return "🔐 CRYPTO"
    if "p2p" in path_lower or "peer" in path_lower or "gossip" in path_lower:
        return "🌐 P2P"
    if "consensus" in path_lower or "ghost" in path_lower or "casper" in path_lower:
        return "⚙️ CONSENSUS"
    if "evm" in path_lower or "vm" in path_lower or "execution" in path_lower:
        return "📜 EVM/VM"
    if "block" in path_lower or "chain" in path_lower or "miner" in path_lower:
        return "⛓️ BLOCKCHAIN"
    if "rpc" in path_lower or "api" in path_lower or "server" in path_lower:
        return "📡 RPC/API"
    if "nft" in path_lower or "marketplace" in path_lower:
        return "🖼️ NFT"
    if "shard" in path_lower:
        return "🧩 SHARDING"
    if "oracle" in path_lower:
        return "📊 ORACLE"
    if "storage" in path_lower or "db" in path_lower or "sqlite" in path_lower:
        return "💾 STORAGE"
    if "websocket" in path_lower or "event" in path_lower:
        return "🔌 WEBSOCKET"
    if "test" in path_lower:
        return "🧪 TEST"
    return "📄 OTHER"

def main():
    print("=" * 70)
    print("🔍 RUNTIME TRUTH AUDITOR")
    print("Анализ реально работающих компонентов")
    print("=" * 70)
    print()
    
    results = {}
    
    for entry_name, entry_file_name in ENTRY_POINTS.items():
        print(f"📌 Анализируем точку входа: {entry_name}")
        print(f"   Файл: {entry_file_name}")
        print()
        
        entry_file = ROOT / entry_file_name
        if not entry_file.exists():
            print(f"   ❌ Файл не найден!")
            continue
        
        # Строим дерево зависимостей
        import_graph, reverse_graph, used_files = build_dependency_tree(entry_file, ROOT)
        
        # Классифицируем компоненты
        components = defaultdict(list)
        for file_path in used_files:
            component = classify_component(str(file_path))
            components[component].append(file_path)
        
        results[entry_name] = {
            "used_files": len(used_files),
            "components": dict(components),
            "import_graph": {str(k): [str(vv) for vv in v] for k, v in import_graph.items()}
        }
        
        # Вывод
        print("=" * 70)
        print(f"📊 РЕЗУЛЬТАТЫ ДЛЯ {entry_name}")
        print("=" * 70)
        print()
        print(f"✅ Реально используется файлов: {len(used_files)}")
        print()
        
        print("📂 ИСПОЛЬЗУЕМЫЕ КОМПОНЕНТЫ:")
        for component, files in sorted(components.items(), key=lambda x: -len(x[1])):
            print(f"\n  {component} ({len(files)} файлов)")
            for f in files[:10]:
                print(f"    📄 {f}")
            if len(files) > 10:
                print(f"    ... и {len(files) - 10} ещё")
        
        print()
        print("=" * 70)
        print("🎯 REAL BLOCKCHAIN CAPABILITIES (ЧТО РЕАЛЬНО РАБОТАЕТ)")
        print("=" * 70)
        
        capabilities = []
        if "🔐 CRYPTO" in components:
            capabilities.append("✅ ECDSA / Wallets")
            if any("zk" in str(f) for f in components["🔐 CRYPTO"]):
                capabilities.append("⚠️ ZK Proofs (требует проверки)")
            if any("sphincs" in str(f) for f in components["🔐 CRYPTO"]):
                capabilities.append("⚠️ SPHINCS+ (требует проверки)")
        
        if "⛓️ BLOCKCHAIN" in components:
            capabilities.append("✅ Blockchain Core / Mining")
        
        if "💾 STORAGE" in components:
            capabilities.append("✅ SQLite / Persistence")
        
        if "📡 RPC/API" in components:
            capabilities.append("✅ JSON-RPC API")
        
        if "🔌 WEBSOCKET" in components:
            capabilities.append("✅ WebSocket Server")
        
        if "🌐 P2P" in components:
            capabilities.append("✅ P2P Network")
        else:
            capabilities.append("❌ P2P НЕ ИСПОЛЬЗУЕТСЯ")
        
        if "⚙️ CONSENSUS" in components:
            capabilities.append("✅ Consensus Engine")
            # Проверяем конкретные алгоритмы
            consensus_files = [str(f) for f in components["⚙️ CONSENSUS"]]
            if any("ghost" in f or "lmd" in f for f in consensus_files):
                capabilities.append("   ├─ LMD-GHOST присутствует")
            else:
                capabilities.append("   ├─ LMD-GHOST ОТСУТСТВУЕТ")
            
            if any("casper" in f for f in consensus_files):
                capabilities.append("   ├─ Casper FFG присутствует")
            else:
                capabilities.append("   ├─ Casper FFG ОТСУТСТВУЕТ")
            
            if any("slashing" in f for f in consensus_files):
                capabilities.append("   └─ Slashing присутствует")
            else:
                capabilities.append("   └─ Slashing ОТСУТСТВУЕТ")
        else:
            capabilities.append("❌ Consensus НЕ ИСПОЛЬЗУЕТСЯ")
        
        if "📜 EVM/VM" in components:
            capabilities.append("✅ EVM / Virtual Machine")
        else:
            capabilities.append("❌ EVM НЕ ИСПОЛЬЗУЕТСЯ")
        
        if "🖼️ NFT" in components:
            capabilities.append("✅ NFT Marketplace")
        else:
            capabilities.append("❌ NFT НЕ ИСПОЛЬЗУЕТСЯ")
        
        if "🧩 SHARDING" in components:
            capabilities.append("✅ Sharding")
        else:
            capabilities.append("❌ Sharding НЕ ИСПОЛЬЗУЕТСЯ")
        
        if "📊 ORACLE" in components:
            capabilities.append("✅ Oracles")
        else:
            capabilities.append("❌ Oracles НЕ ИСПОЛЬЗУЮТСЯ")
        
        for cap in capabilities:
            print(f"  {cap}")
        
        print()
        print("=" * 70)
        print("⚠️ ЧТО НЕ РАБОТАЕТ (есть в проекте, но не используется)")
        print("=" * 70)
        
        # Проверяем известные модули на использование
        check_modules = {
            "SPHINCS+": ["sphincs", "postquantum"],
            "ZK Proofs": ["zk_", "zero_knowledge"],
            "Lightning Network": ["lightning"],
            "Cross-chain Bridge": ["bridge", "crosschain"],
            "AI Consensus": ["ai_consensus", "ai_validator"],
            "Plasma": ["plasma"],
            "WASM": ["wasm"],
        }
        
        for name, patterns in check_modules.items():
            found = False
            for pattern in patterns:
                for f in used_files:
                    if pattern in str(f).lower():
                        found = True
                        break
                if found:
                    break
            if not found:
                print(f"  ❌ {name}")
        
        print()
    
    # Сохраняем отчёт
    report_path = ROOT / "runtime_truth_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        # Конвертируем Path в строки для JSON
        json_results = {}
        for entry, data in results.items():
            json_results[entry] = {
                "used_files": data["used_files"],
                "components": {k: [str(vv) for vv in v] for k, v in data["components"].items()}
            }
        json.dump(json_results, f, indent=2, ensure_ascii=False)
    
    print()
    print("=" * 70)
    print(f"📄 Полный отчёт: {report_path}")
    print("=" * 70)

if __name__ == "__main__":
    main()