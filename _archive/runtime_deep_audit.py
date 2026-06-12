#!/usr/bin/env python3
"""
RUNTIME DEEP AUDIT - Полный анализ всех точек входа
Проверяет: imports, class usage, function calls, thread starts
"""

import ast
import sys
import json
import re
from pathlib import Path
from collections import defaultdict
from typing import Set, Dict, List, Tuple

ROOT = Path(r"C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate")

# Все потенциальные точки входа
ENTRY_POINTS = {
    "main": "main.py",
    "run_unified": "run_unified.py", 
    "node_persistent": "node_persistent.py",
    "ABSOLUTE_FINAL_FIXED": "ABSOLUTE_FINAL_FIXED.py",
    "ABSOLUTE_UNIFIED": "ABSOLUTE_UNIFIED.py",
    "ABSOLUTE_UNIFIED_FULL": "ABSOLUTE_UNIFIED_FULL.py",
}

def find_module_file(module_name: str, root: Path) -> Path | None:
    """Находит файл по имени модуля"""
    # Прямой файл
    direct = root / f"{module_name}.py"
    if direct.exists():
        return direct
    
    # В подпапках
    for py in root.rglob("*.py"):
        if py.stem == module_name and "__pycache__" not in str(py):
            return py
    
    # Как пакет
    pkg = root / module_name / "__init__.py"
    if pkg.exists():
        return pkg
    
    return None

def analyze_file_deep(file_path: Path) -> Dict:
    """Глубокий анализ файла"""
    result = {
        "imports": set(),
        "classes": set(),
        "function_calls": set(),
        "thread_starts": [],
        "async_tasks": [],
        "api_routes": [],
        "websocket_starts": [],
        "init_calls": set()
    }
    
    try:
        source = file_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source)
        
        for node in ast.walk(tree):
            # Импорты
            if isinstance(node, ast.Import):
                for alias in node.names:
                    result["imports"].add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module and not node.module.startswith('.'):
                    result["imports"].add(node.module.split('.')[0])
            
            # Классы
            if isinstance(node, ast.ClassDef):
                result["classes"].add(node.name)
            
            # Вызовы функций
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    result["function_calls"].add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    result["function_calls"].add(node.func.attr)
            
            # Thread starts
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ['start', 'start_new_thread']:
                        result["thread_starts"].append(ast.unparse(node))
            
            # Async tasks
            if isinstance(node, ast.Await):
                result["async_tasks"].append(ast.unparse(node))
            
            # API routes (FastAPI/Flask)
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ['get', 'post', 'put', 'delete', 'route', 'app']:
                        result["api_routes"].append(ast.unparse(node))
            
            # WebSocket starts
            if "websocket" in source.lower() and "serve" in source.lower():
                result["websocket_starts"].append("websocket detected")
            
            # Инициализация компонентов
            init_patterns = ['consensus', 'p2p', 'sharding', 'oracle', 'nft', 'zk', 'evm', 'miner']
            for pattern in init_patterns:
                if pattern in source.lower() and ('init' in source.lower() or 'start' in source.lower()):
                    result["init_calls"].add(pattern)
    
    except Exception as e:
        pass
    
    return result

def build_dependency_tree(entry_file: Path, root: Path, max_depth: int = 15) -> Dict:
    """Строит полное дерево зависимостей"""
    visited = set()
    import_graph = defaultdict(set)
    file_analysis = {}
    
    def traverse(file_path: Path, depth: int = 0):
        if depth > max_depth:
            return
        if file_path in visited:
            return
        visited.add(file_path)
        
        analysis = analyze_file_deep(file_path)
        file_analysis[file_path] = analysis
        
        for imp in analysis["imports"]:
            dep_file = find_module_file(imp, root)
            if dep_file and dep_file != file_path:
                import_graph[file_path].add(dep_file)
                traverse(dep_file, depth + 1)
    
    traverse(entry_file)
    return {
        "used_files": visited,
        "import_graph": import_graph,
        "file_analysis": file_analysis
    }

def classify_component(file_path: Path) -> str:
    """Классифицирует файл по содержимому"""
    path_str = str(file_path).lower()
    content = ""
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore").lower()
    except:
        pass
    
    if any(x in path_str or x in content for x in ['crypto', 'wallet', 'sign', 'ecdsa', 'hash']):
        return "🔐 CRYPTO"
    if any(x in path_str or x in content for x in ['p2p', 'peer', 'gossip', 'discovery']):
        return "🌐 P2P"
    if any(x in path_str or x in content for x in ['consensus', 'ghost', 'casper', 'validator', 'slashing']):
        return "⚙️ CONSENSUS"
    if any(x in path_str or x in content for x in ['evm', 'vm', 'opcode', 'gas', 'execute']):
        return "📜 EVM/VM"
    if any(x in path_str or x in content for x in ['block', 'chain', 'miner', 'mine']):
        return "⛓️ BLOCKCHAIN"
    if any(x in path_str or x in content for x in ['rpc', 'api', 'server', 'endpoint']):
        return "📡 RPC/API"
    if any(x in path_str or x in content for x in ['nft', 'marketplace', 'mint']):
        return "🖼️ NFT"
    if any(x in path_str or x in content for x in ['shard']):
        return "🧩 SHARDING"
    if any(x in path_str or x in content for x in ['oracle', 'price', 'weather']):
        return "📊 ORACLE"
    if any(x in path_str or x in content for x in ['storage', 'sqlite', 'db']):
        return "💾 STORAGE"
    if any(x in path_str or x in content for x in ['websocket', 'event']):
        return "🔌 WEBSOCKET"
    if any(x in path_str or x in content for x in ['test_', 'pytest']):
        return "🧪 TEST"
    return "📄 OTHER"

def audit_entry_point(entry_name: str, entry_file: Path) -> Dict:
    """Аудит одной точки входа"""
    print(f"\n{'='*70}")
    print(f"📌 Анализ: {entry_name}")
    print(f"   Файл: {entry_file}")
    print(f"{'='*70}\n")
    
    if not entry_file.exists():
        print(f"   ❌ Файл не найден!\n")
        return None
    
    # Строим дерево
    result = build_dependency_tree(entry_file, ROOT)
    used_files = result["used_files"]
    file_analysis = result["file_analysis"]
    
    # Классифицируем
    components = defaultdict(set)
    for f in used_files:
        comp = classify_component(f)
        components[comp].add(f)
    
    # Собираем capabilities
    capabilities = []
    init_calls_all = set()
    thread_starts = []
    api_routes = []
    
    for f, analysis in file_analysis.items():
        init_calls_all.update(analysis["init_calls"])
        thread_starts.extend(analysis["thread_starts"])
        api_routes.extend(analysis["api_routes"])
    
    # Определяем работающие компоненты
    if "⛓️ BLOCKCHAIN" in components:
        capabilities.append("✅ Blockchain Core / Mining")
    else:
        capabilities.append("❌ Blockchain Core")
    
    if "💾 STORAGE" in components:
        capabilities.append("✅ Storage / Persistence")
    else:
        capabilities.append("❌ Storage")
    
    if "📡 RPC/API" in components:
        capabilities.append("✅ RPC/API")
    else:
        capabilities.append("❌ RPC/API")
    
    if "🔌 WEBSOCKET" in components:
        capabilities.append("✅ WebSocket")
    else:
        capabilities.append("❌ WebSocket")
    
    if "🌐 P2P" in components and "p2p" in init_calls_all:
        capabilities.append("✅ P2P Network")
    else:
        capabilities.append("❌ P2P Network")
    
    if "⚙️ CONSENSUS" in components and any(x in init_calls_all for x in ['consensus', 'ghost', 'casper']):
        capabilities.append("✅ Consensus Engine")
    else:
        capabilities.append("❌ Consensus Engine")
    
    if "📜 EVM/VM" in components:
        capabilities.append("✅ EVM/Virtual Machine")
    else:
        capabilities.append("❌ EVM/VM")
    
    if "🖼️ NFT" in components:
        capabilities.append("✅ NFT Marketplace")
    else:
        capabilities.append("❌ NFT Marketplace")
    
    if "🧩 SHARDING" in components:
        capabilities.append("✅ Sharding")
    else:
        capabilities.append("❌ Sharding")
    
    if "📊 ORACLE" in components:
        capabilities.append("✅ Oracles")
    else:
        capabilities.append("❌ Oracles")
    
    return {
        "entry": entry_name,
        "used_files_count": len(used_files),
        "components": {k: len(v) for k, v in components.items()},
        "capabilities": capabilities,
        "init_calls": list(init_calls_all),
        "threads": len(thread_starts),
        "api_routes": len(api_routes)
    }

def main():
    print("=" * 70)
    print("🔍 RUNTIME DEEP AUDIT")
    print("Анализ всех точек входа")
    print("=" * 70)
    
    results = []
    
    for entry_name, entry_file_name in ENTRY_POINTS.items():
        entry_file = ROOT / entry_file_name
        result = audit_entry_point(entry_name, entry_file)
        if result:
            results.append(result)
    
    # Сравнительная таблица
    print("\n" + "=" * 70)
    print("📊 СРАВНИТЕЛЬНЫЙ АНАЛИЗ ВСЕХ ТОЧЕК ВХОДА")
    print("=" * 70)
    
    print(f"\n{'Точка входа':<25} {'Файлов':<8} {'Компонентов':<12} {'Capabilities':<30}")
    print("-" * 80)
    
    for r in results:
        caps_count = len([c for c in r["capabilities"] if c.startswith("✅")])
        print(f"{r['entry']:<25} {r['used_files_count']:<8} {len(r['components']):<12} {caps_count}/11")
    
    # Детально по каждой
    for r in results:
        print(f"\n{'='*70}")
        print(f"📌 {r['entry']}")
        print(f"{'='*70}")
        print(f"\n📁 Использует файлов: {r['used_files_count']}")
        print(f"📦 Компонентов: {len(r['components'])}")
        print(f"⚙️ Инициализирует: {', '.join(r['init_calls']) if r['init_calls'] else 'НИЧЕГО'}")
        print(f"🧵 Потоков: {r['threads']}")
        print(f"🌐 API маршрутов: {r['api_routes']}")
        print(f"\n🎯 CAPABILITIES:")
        for cap in r["capabilities"]:
            print(f"   {cap}")
    
    # Главный вывод
    print("\n" + "=" * 70)
    print("🏆 ГЛАВНЫЙ ВЫВОД")
    print("=" * 70)
    
    # Находим лучшую точку входа
    best = max(results, key=lambda x: x["used_files_count"] if x else 0)
    
    print(f"\n📌 ЛУЧШАЯ ТОЧКА ВХОДА: {best['entry']}")
    print(f"   Использует {best['used_files_count']} файлов")
    print(f"   Инициализирует: {', '.join(best['init_calls']) if best['init_calls'] else 'НИЧЕГО'}")
    
    working_caps = [c for c in best["capabilities"] if c.startswith("✅")]
    print(f"\n✅ РАБОТАЕТ ({len(working_caps)}/11):")
    for cap in working_caps:
        print(f"   {cap}")
    
    missing_caps = [c for c in best["capabilities"] if c.startswith("❌")]
    print(f"\n❌ НЕ РАБОТАЕТ ({len(missing_caps)}/11):")
    for cap in missing_caps:
        print(f"   {cap}")
    
    # Сохраняем отчёт
    report_path = ROOT / "runtime_deep_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n📄 Полный отчёт: {report_path}")
    print("=" * 70)

if __name__ == "__main__":
    main()