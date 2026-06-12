#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from runtime.orchestrator import Orchestrator

if __name__ == "__main__":
    try:
        orchestrator = Orchestrator()
        orchestrator.start()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        orchestrator.stop()
