#!/usr/bin/env python3
"""
ARCHITECTURE AUDITOR - Глубокий анализ блокчейн-проекта
Ничего не удаляет, только анализирует
"""

import os
import ast
import json
import hashlib
from pathlib import Path
from collections import defaultdict
from datetime import datetime

ROOT = Path(r"C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate")

# Классификация компонентов
COMPONENTS = {
    'core': ['block', 'chain', 'utxo', 'transaction', 'miner'],
    'consensus': ['consensus', 'ghost', 'casper', 'validator', 'slashing', 'finality', 'epoch'],
    'execution': ['evm', 'vm', 'opcode', 'gas', 'execute', 'contract', 'sstore', 'sload'],
    'network': ['p2p', 'peer', 'gossip', 'discovery', 'handshake', 'sync'],
    'storage': ['storage', 'database', 'sqlite', 'rocksdb', 'persist', 'snapshot'],
    'rpc': ['rpc', 'jsonrpc', 'eth_', 'web3'],
    'api': ['api', 'fastapi', 'flask', 'endpoint', 'route', 'rest'],
    'services': ['indexer', 'event', 'bus', 'orchestrator', 'launcher'],
    'web': ['html', 'css', 'javascript', 'frontend', 'explorer', 'gallery'],
    'crypto': ['crypto', 'ecdsa', 'hash', 'sign', 'verify', 'wallet', 'key'],
    'tests': ['test_', 'pytest', 'unittest', 'assert']
}

# Точки входа для анализа
ENTRY_CANDIDATES = [
    'ABSOLUTE_FINAL_FIXED.py',
    'node_persistent.py', 
    'main.py',
    'run_unified.py',
    'ABSOLUTE_UNIFIED.py',
    'ABSOLUTE_UNIFIED_FULL.py'
]

# Директории для проверки дублей
DUPLICATE_DIRS = [
    '',
    'absolute-blockchain-ultimate',
    'services',
    'api', 
    'rpc',
    'network',
    'p2p',
    'core',
    'consensus'
]

class ArchitectureAuditor:
    def __init__(self):
        self.results = {
            'files': {},
            'imports': {},
            'duplicates': {},
            'dead_code': [],
            'entry_points': [],
            'canonical_candidates': {},
            'issues': []
        }
        self.all_files = []
        self.content_cache = {}
    
    def scan_files(self):
        """Сканирует все Python файлы"""
        print("\n📁 СКАНИРОВАНИЕ ФАЙЛОВ...")
        for py_file in ROOT.rglob("*.py"):
            # Пропускаем временные и служебные
            if any(x in str(py_file) for x in ['__pycache__', '.venv', 'venv', 'backup', 'temp']):
                continue
            rel_path = py_file.relative_to(ROOT)
            self.all_files.append(rel_path)
            self.results['files'][str(rel_path)] = {
                'size': py_file.stat().st_size,
                'modified': py_file.stat().st_mtime,
                'hash': hashlib.md5(py_file.read_bytes()).hexdigest()[:16]
            }
        
        print(f"   ✅ Найдено файлов: {len(self.all_files)}")
    
    def analyze_entry_points(self):
        """Находит настоящие точки входа"""
        print("\n🎯 ПОИСК ТОЧЕК ВХОДА...")
        
        for candidate in ENTRY_CANDIDATES:
            file_path = ROOT / candidate
            if file_path.exists():
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                
                # Проверяем наличие main-блока
                has_main = 'if __name__ == "__main__"' in content
                
                # Проверяем импорты
                imports = self._extract_imports(content)
                
                # Проверяем запуск серверов
                has_server = any(x in content.lower() for x in ['run(', 'serve(', 'start(', 'threading']))
                
                self.results['entry_points'].append({
                    'file': candidate,
                    'has_main': has_main,
                    'imports_count': len(imports),
                    'has_server': has_server,
                    'score': (has_main * 2) + (has_server * 1) + min(len(imports), 10)
                })
        
        # Сортируем по score
        self.results['entry_points'].sort(key=lambda x: x['score'], reverse=True)
        
        print(f"   ✅ Лучшая точка входа: {self.results['entry_points'][0]['file'] if self.results['entry_points'] else 'не найдена'}")
    
    def analyze_imports(self):
        """Анализирует импорты и зависимости"""
        print("\n🔗 АНАЛИЗ ИМПОРТОВ...")
        
        import_graph = defaultdict(set)
        
        for file_path in self.all_files:
            full_path = ROOT / file_path
            content = full_path.read_text(encoding='utf-8', errors='ignore')
            
            imports = self._extract_imports(content)
            import_graph[str(file_path)] = imports
            
            # Проверяем битые импорты
            for imp in imports:
                imp_file = self._find_module(imp)
                if not imp_file:
                    self.results['issues'].append({
                        'type': 'broken_import',
                        'file': str(file_path),
                        'import': imp
                    })
        
        self.results['imports'] = {k: list(v) for k, v in import_graph.items()}
        
        print(f"   ✅ Импортов проанализировано: {len(import_graph)}")
        print(f"   ⚠️ Битых импортов: {len(self.results['issues'])}")
    
    def find_duplicates(self):
        """Находит дубликаты файлов"""
        print("\n🔄 ПОИСК ДУБЛИКАТОВ...")
        
        by_name = defaultdict(list)
        by_hash = defaultdict(list)
        
        for file_path in self.all_files:
            name = file_path.name
            by_name[name].append(str(file_path))
            
            file_hash = self.results['files'][str(file_path)]['hash']
            by_hash[file_hash].append(str(file_path))
        
        # Дубликаты по имени
        name_dups = {name: paths for name, paths in by_name.items() if len(paths) > 1}
        
        # Точные дубликаты по хэшу
        exact_dups = {h: paths for h, paths in by_hash.items() if len(paths) > 1}
        
        self.results['duplicates'] = {
            'by_name': dict(name_dups),
            'exact': dict(exact_dups)
        }
        
        print(f"   ✅ Дубликатов по имени: {len(name_dups)}")
        print(f"   ✅ Точных дубликатов: {len(exact_dups)}")
    
    def classify_status(self):
        """Классифицирует каждый файл: ACTIVE, LEGACY, DUPLICATE, UNUSED"""
        print("\n📊 КЛАССИФИКАЦИЯ ФАЙЛОВ...")
        
        # Находим активные файлы (используются в импортах)
        used_files = set()
        for imp_list in self.results['imports'].values():
            used_files.update(imp_list)
        
        # Также файлы с импортами считаем активными
        for file_path in self.results['imports'].keys():
            used_files.add(file_path)
        
        # Добавляем entry points
        for ep in self.results['entry_points']:
            used_files.add(ep['file'])
        
        # Классифицируем каждый файл
        for file_path in self.all_files:
            str_path = str(file_path)
            status = 'UNUSED'
            reason = ''
            
            # Проверка на дубликат
            is_duplicate = any(str_path in paths for paths in self.results['duplicates']['by_name'].values())
            if is_duplicate:
                status = 'DUPLICATE'
                reason = 'Есть копия с таким же именем'
            
            # Проверка на активность
            elif str_path in used_files:
                status = 'ACTIVE'
                reason = 'Используется в импортах'
            
            # Проверка на LEGACY (старые версии, бэкапы)
            elif any(x in str_path.lower() for x in ['backup', 'old', 'deprecated', 'v42', 'v45']):
                status = 'LEGACY'
                reason = 'Старая версия или бэкап'
            
            # UNUSED - остальные
            else:
                status = 'UNUSED'
                reason = 'Не импортируется нигде'
            
            self.results['files'][str_path]['status'] = status
            self.results['files'][str_path]['reason'] = reason
    
    def find_canonical_candidates(self):
        """Находит канонические файлы для каждого компонента"""
        print("\n🏆 ПОИСК КАНОНИЧЕСКИХ ФАЙЛОВ...")
        
        for component, keywords in COMPONENTS.items():
            candidates = []
            
            for file_path in self.all_files:
                str_path = str(file_path).lower()
                content = self._get_content(ROOT / file_path).lower()
                
                # Проверяем по ключевым словам
                score = 0
                for kw in keywords:
                    if kw in str_path or kw in content:
                        score += 1
                
                if score > 0 and self.results['files'][str(file_path)]['status'] == 'ACTIVE':
                    candidates.append((str(file_path), score))
            
            if candidates:
                candidates.sort(key=lambda x: x[1], reverse=True)
                self.results['canonical_candidates'][component] = candidates[0][0]
        
        print(f"   ✅ Найдено канонических файлов: {len(self.results['canonical_candidates'])}")
    
    def analyze_components(self):
        """Анализирует компоненты и их использование"""
        print("\n🧩 АНАЛИЗ КОМПОНЕНТОВ...")
        
        component_stats = defaultdict(lambda: {'total': 0, 'active': 0, 'legacy': 0, 'duplicate': 0, 'unused': 0})
        
        for file_path, info in self.results['files'].items():
            # Определяем компонент
            component = 'other'
            file_lower = file_path.lower()
            
            for comp, keywords in COMPONENTS.items():
                if any(kw in file_lower for kw in keywords):
                    component = comp
                    break
            
            component_stats[component]['total'] += 1
            component_stats[component][info['status'].lower()] += 1
        
        self.results['components'] = dict(component_stats)
        
        print(f"   ✅ Проанализировано компонентов: {len(component_stats)}")
    
    def _extract_imports(self, content):
        """Извлекает импорты из кода"""
        imports = []
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module.split('.')[0])
        except:
            pass
        return list(set(imports))
    
    def _find_module(self, module_name):
        """Находит файл модуля"""
        for file_path in self.all_files:
            if file_path.stem == module_name or file_path.name == f"{module_name}.py":
                return file_path
        return None
    
    def _get_content(self, file_path):
        """Кэширует содержимое файлов"""
        str_path = str(file_path)
        if str_path not in self.content_cache:
            try:
                self.content_cache[str_path] = file_path.read_text(encoding='utf-8', errors='ignore')
            except:
                self.content_cache[str_path] = ''
        return self.content_cache[str_path]
    
    def generate_report(self):
        """Генерирует финальный отчёт"""
        print("\n📄 ГЕНЕРАЦИЯ ОТЧЁТА...")
        
        report_lines = []
        report_lines.append("# ARCHITECTURE AUDIT REPORT\n")
        report_lines.append(f"**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        report_lines.append(f"**Проект:** Absolute Blockchain Ultimate\n")
        report_lines.append(f"**Всего файлов:** {len(self.all_files)}\n")
        
        # Точки входа
        report_lines.append("\n## 🎯 ТОЧКИ ВХОДА\n")
        report_lines.append("| Файл | Main блок | Импортов | Сервер | Score |\n")
        report_lines.append("|------|-----------|----------|--------|-------|\n")
        for ep in self.results['entry_points']:
            report_lines.append(f"| {ep['file']} | {ep['has_main']} | {ep['imports_count']} | {ep['has_server']} | {ep['score']} |\n")
        
        # Статистика
        report_lines.append("\n## 📊 СТАТИСТИКА\n")
        total = len(self.all_files)
        active = sum(1 for f in self.results['files'].values() if f['status'] == 'ACTIVE')
        legacy = sum(1 for f in self.results['files'].values() if f['status'] == 'LEGACY')
        duplicate = sum(1 for f in self.results['files'].values() if f['status'] == 'DUPLICATE')
        unused = sum(1 for f in self.results['files'].values() if f['status'] == 'UNUSED')
        
        report_lines.append(f"- **ACTIVE:** {active} ({active/total*100:.1f}%)\n")
        report_lines.append(f"- **LEGACY:** {legacy} ({legacy/total*100:.1f}%)\n")
        report_lines.append(f"- **DUPLICATE:** {duplicate} ({duplicate/total*100:.1f}%)\n")
        report_lines.append(f"- **UNUSED:** {unused} ({unused/total*100:.1f}%)\n")
        
        # Канонические кандидаты
        report_lines.append("\n## 🏆 КАНОНИЧЕСКИЕ ФАЙЛЫ\n")
        for component, file_path in self.results['canonical_candidates'].items():
            report_lines.append(f"- **{component}:** `{file_path}`\n")
        
        # Дубликаты
        report_lines.append("\n## 🔄 ДУБЛИКАТЫ\n")
        for name, paths in self.results['duplicates']['by_name'].items():
            if len(paths) > 1:
                report_lines.append(f"\n### `{name}`\n")
                for p in paths:
                    status = self.results['files'][p]['status']
                    report_lines.append(f"  - {p} [{status}]\n")
        
        # Битые импорты
        if self.results['issues']:
            report_lines.append("\n## ⚠️ БИТЫЕ ИМПОРТЫ\n")
            for issue in self.results['issues'][:20]:
                report_lines.append(f"- `{issue['file']}` → `{issue['import']}`\n")
        
        # Компоненты
        report_lines.append("\n## 🧩 КОМПОНЕНТЫ\n")
        report_lines.append("| Компонент | Всего | ACTIVE | LEGACY | DUPLICATE | UNUSED |\n")
        report_lines.append("|----------|-------|--------|--------|-----------|--------|\n")
        for comp, stats in sorted(self.results['components'].items()):
            report_lines.append(f"| {comp} | {stats['total']} | {stats['active']} | {stats['legacy']} | {stats['duplicate']} | {stats['unused']} |\n")
        
        # Детальный список файлов
        report_lines.append("\n## 📁 ДЕТАЛЬНЫЙ СПИСОК ФАЙЛОВ\n")
        report_lines.append("| Файл | Статус | Причина | Заменён на |\n")
        report_lines.append("|------|--------|---------|------------|\n")
        
        for file_path, info in sorted(self.results['files'].items()):
            replaced = ''
            # Проверяем, есть ли каноническая замена
            for comp, canonical in self.results['canonical_candidates'].items():
                if file_path != canonical and file_path.split('/')[-1] == canonical.split('/')[-1]:
                    replaced = canonical
                    break
            
            report_lines.append(f"| `{file_path}` | {info['status']} | {info['reason']} | `{replaced}` |\n")
        
        # Сохраняем отчёт
        report_path = ROOT / "ARCHITECTURE_AUDIT.md"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.writelines(report_lines)
        
        # Сохраняем JSON для дальнейшего использования
        json_path = ROOT / "architecture_audit.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        print(f"   ✅ Отчёт сохранён: {report_path}")
        print(f"   ✅ JSON сохранён: {json_path}")
    
    def print_summary(self):
        """Выводит краткую сводку"""
        print("\n" + "="*70)
        print("📊 КРАТКАЯ СВОДКА")
        print("="*70)
        
        print(f"\n📁 Всего файлов: {len(self.all_files)}")
        
        active = sum(1 for f in self.results['files'].values() if f['status'] == 'ACTIVE')
        legacy = sum(1 for f in self.results['files'].values() if f['status'] == 'LEGACY')
        duplicate = sum(1 for f in self.results['files'].values() if f['status'] == 'DUPLICATE')
        unused = sum(1 for f in self.results['files'].values() if f['status'] == 'UNUSED')
        
        print(f"\n✅ ACTIVE: {active} (реально используется)")
        print(f"📜 LEGACY: {legacy} (старые версии)")
        print(f"🔄 DUPLICATE: {duplicate} (дубликаты)")
        print(f"🗑️ UNUSED: {unused} (не используется)")
        
        print(f"\n🎯 Лучшая точка входа: {self.results['entry_points'][0]['file'] if self.results['entry_points'] else 'не найдена'}")
        
        print(f"\n🏆 Канонические файлы найдены для {len(self.results['canonical_candidates'])} компонентов")
        
        print(f"\n⚠️ Проблем: {len(self.results['issues'])} (битые импорты)")

def main():
    print("="*70)
    print("🏗️ ARCHITECTURE AUDITOR - Глубокий анализ блокчейн-проекта")
    print("Ничего не удаляется, только анализ")
    print("="*70)
    
    auditor = ArchitectureAuditor()
    
    auditor.scan_files()
    auditor.analyze_entry_points()
    auditor.analyze_imports()
    auditor.find_duplicates()
    auditor.classify_status()
    auditor.find_canonical_candidates()
    auditor.analyze_components()
    auditor.generate_report()
    auditor.print_summary()
    
    print("\n" + "="*70)
    print("✅ АУДИТ ЗАВЕРШЁН")
    print("="*70)
    print("\n📄 Отчёт: ARCHITECTURE_AUDIT.md")
    print("📊 JSON: architecture_audit.json")
    print("\n⚠️ Ничего не удалено. Только анализ.")
    print("="*70)

if __name__ == "__main__":
    main()