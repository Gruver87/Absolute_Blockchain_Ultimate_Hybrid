#!/usr/bin/env python3
"""
DEPENDENCY AUDITOR - Реальный анализ импортов
Показывает, какие файлы действительно используются, а какие - нет
"""

import ast
import json
import sys
from pathlib import Path
from collections import defaultdict, Counter

ROOT = Path(r"C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate")

# Игнорируем эти папки
IGNORE = {
    ".git", "__pycache__", ".venv", "venv", "env",
    "backups", "backup", ".idea", ".vscode", "logs",
    "data", "nft_images", "__pycache__", "node_modules",
    "rust_blockchain/target", ".pytest_cache"
}

# Файлы, которые точно являются точками входа
ENTRY_PATTERNS = [
    "main", "run_unified", "node_persistent", "run_node",
    "rpc_server", "extended_api_server", "ABSOLUTE_FINAL_FIXED",
    "ABSOLUTE_UNIFIED", "ABSOLUTE_UNIFIED_FULL", "runtime"
]

def normalize_module_name(file_path: Path, root: Path) -> str:
    """Преобразует путь файла в имя модуля Python"""
    rel = file_path.relative_to(root)
    # Убираем расширение .py
    parts = list(rel.with_suffix("").parts)
    # Если есть __init__.py, убираем его
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)

def get_imports_from_file(file_path: Path) -> list:
    """Извлекает все импорты из Python файла"""
    imports = []
    try:
        source = file_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name.split('.')[0])  # Только корневой модуль
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    # Пропускаем относительные импорты
                    if not node.module.startswith('.'):
                        imports.append(node.module.split('.')[0])
    except Exception:
        pass
    return list(set(imports))

def main():
    print("=" * 70)
    print("🔍 DEPENDENCY AUDITOR - Анализ импортов")
    print("=" * 70)
    print(f"📁 Сканируем: {ROOT}")
    print()
    
    # Собираем все Python файлы
    python_files = []
    for py in ROOT.rglob("*.py"):
        # Пропускаем игнорируемые папки
        if any(ign in py.parts for ign in IGNORE):
            continue
        python_files.append(py)
    
    print(f"📊 Найдено Python файлов: {len(python_files)}")
    print()
    
    # Создаём карту модулей
    module_map = {}
    for py in python_files:
        module_name = normalize_module_name(py, ROOT)
        if module_name:  # Пропускаем пустые
            module_map[module_name] = py
    
    print(f"📦 Уникальных модулей: {len(module_map)}")
    print()
    
    # Анализируем импорты
    imports_graph = defaultdict(set)
    reverse_graph = defaultdict(set)
    
    for module_name, file_path in module_map.items():
        imports = get_imports_from_file(file_path)
        for imp in imports:
            if imp in module_map:  # Только существующие модули
                imports_graph[module_name].add(imp)
                reverse_graph[imp].add(module_name)
    
    # Находим точки входа
    entry_candidates = []
    for module_name in module_map:
        for pattern in ENTRY_PATTERNS:
            if pattern.lower() in module_name.lower():
                entry_candidates.append(module_name)
                break
    
    # Находим мёртвые модули (никто не импортирует)
    unused_modules = []
    for module_name in module_map:
        if module_name not in reverse_graph and module_name not in entry_candidates:
            # Пропускаем __init__ и конфиги
            if not module_name.endswith("__init__"):
                unused_modules.append(module_name)
    
    # Анализируем дубликаты (файлы с одинаковыми именами)
    name_counter = Counter()
    for module_name in module_map:
        base_name = module_name.split('.')[-1]
        name_counter[base_name] += 1
    
    duplicates = {name: count for name, count in name_counter.items() if count > 1}
    
    # Строим дерево зависимостей для main
    def build_dependency_tree(module, depth=0, visited=None):
        if visited is None:
            visited = set()
        if module in visited or depth > 10:
            return []
        visited.add(module)
        result = [("  " * depth) + f"📄 {module}"]
        for dep in sorted(imports_graph.get(module, [])):
            result.extend(build_dependency_tree(dep, depth + 1, visited))
        return result
    
    # Вывод результатов
    print("=" * 70)
    print("🎯 ТОЧКИ ВХОДА (entry points)")
    print("=" * 70)
    for entry in sorted(set(entry_candidates)):
        print(f"  ✅ {entry}")
    
    print()
    print("=" * 70)
    print("📊 СТАТИСТИКА")
    print("=" * 70)
    print(f"  Всего модулей:      {len(module_map)}")
    print(f"  Используется:       {len(module_map) - len(unused_modules)}")
    print(f"  Не используется:    {len(unused_modules)}")
    print(f"  Точки входа:        {len(set(entry_candidates))}")
    print(f"  Дубликатов имён:    {len(duplicates)}")
    
    print()
    print("=" * 70)
    print("🔄 ДЕРЕВО ЗАВИСИМОСТЕЙ (для main)")
    print("=" * 70)
    
    # Пробуем найти основной entry point
    main_entry = None
    for entry in ["main", "run_unified", "node_persistent", "ABSOLUTE_FINAL_FIXED"]:
        found = [m for m in entry_candidates if entry in m]
        if found:
            main_entry = found[0]
            break
    
    if main_entry:
        print(f"\n📌 Базовый модуль: {main_entry}\n")
        tree = build_dependency_tree(main_entry)
        for line in tree:
            print(line)
    else:
        print("  Не найден основной модуль main")
    
    print()
    print("=" * 70)
    print("🗑️ НЕИСПОЛЬЗУЕМЫЕ МОДУЛИ (первые 50)")
    print("=" * 70)
    for module in sorted(unused_modules)[:50]:
        file_path = module_map.get(module, "?")
        print(f"  ❌ {module}")
        print(f"      {file_path}")
    
    if len(unused_modules) > 50:
        print(f"  ... и ещё {len(unused_modules) - 50}")
    
    print()
    print("=" * 70)
    print("🔄 ДУБЛИКАТЫ ИМЁН МОДУЛЕЙ")
    print("=" * 70)
    for name, count in sorted(duplicates.items(), key=lambda x: -x[1]):
        if count > 1:
            print(f"  📁 {name} -> {count} файлов")
            modules = [m for m in module_map if m.endswith(f".{name}") or m == name]
            for mod in modules:
                print(f"      {mod}")

    print()
    print("=" * 70)
    print("💡 РЕКОМЕНДАЦИИ")
    print("=" * 70)
    
    if len(unused_modules) > 100:
        print("  ⚠️ Много неиспользуемых модулей - пора чистить проект")
    
    if len(entry_candidates) > 3:
        print("  ⚠️ Много точек входа - оставьте только одну (main.py)")
        print(f"     Сейчас: {', '.join(set(entry_candidates))}")
    
    if duplicates:
        print("  ⚠️ Есть дубликаты - удалите лишние версии файлов")
    
    # Сохраняем отчёт
    report = {
        "summary": {
            "total_modules": len(module_map),
            "used_modules": len(module_map) - len(unused_modules),
            "unused_modules": len(unused_modules),
            "entry_points": len(set(entry_candidates)),
            "duplicates": len(duplicates)
        },
        "entry_candidates": sorted(set(entry_candidates)),
        "unused_modules": sorted(unused_modules)[:200],
        "duplicates": {k: v for k, v in duplicates.items() if v > 1}
    }
    
    report_path = ROOT / "dependency_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print()
    print("=" * 70)
    print(f"📄 Отчёт сохранён: {report_path}")
    print("=" * 70)

if __name__ == "__main__":
    main()