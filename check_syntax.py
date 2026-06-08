import os
import py_compile

print("Проверка синтаксиса всех .py файлов...")
errors = []
for root, dirs, files in os.walk("."):
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            try:
                py_compile.compile(path, doraise=True)
            except Exception as e:
                errors.append(f"[ERROR] {path}: {e}")
                print(f"❌ {path}")

if not errors:
    print("✅ Все файлы синтаксически корректны!")
else:
    print(f"\n⚠️ Найдено {len(errors)} файлов с ошибками")
