import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rpc.json_rpc_server import start_json_rpc_server

print("=" * 60)
print("Absolute Blockchain JSON-RPC Server v53")
print("=" * 60)

server = start_json_rpc_server()

print("\n✅ Server is running...")
print("Press Ctrl+C to stop\n")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n🛑 Server stopped")
