# -*- coding: utf-8 -*-
"""Legacy scripts: ensure repo root is on sys.path when run via pytest."""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
