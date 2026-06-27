#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DEPRECATED — используйте main.py как единственную точку входа.

    python main.py
"""

import sys
import os

if __name__ == "__main__":
    print("[node_persistent] Deprecated. Starting unified node via main.py ...")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from main import main
    main()
