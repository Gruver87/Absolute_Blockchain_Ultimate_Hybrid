import os
import re

PROJECT_DIR = r"C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate"

ENTRY_PATTERNS = [
    r'__main__',
    r'FastAPI',
    r'Flask',
    r'serve_forever',
    r'uvicorn',
    r'JSONRPCServer',
    r'P2P',
    r'node_persistent',
    r'extended_api_server',
    r'rpc_proxy',
]

def scan_file(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return [p for p in ENTRY_PATTERNS if re.search(p, content)]
    except:
        return []

def main():
    print("\n=== SCANNING PROJECT ===\n")

    results = []

    for root, _, files in os.walk(PROJECT_DIR):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                hits = scan_file(path)

                if hits:
                    results.append((path, hits))

    for path, hits in results:
        print("\nFILE:", path)
        for h in hits:
            print("  -", h)

    print("\n=== DONE ===")

if __name__ == "__main__":
    main()