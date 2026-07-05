import importlib.util
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from storage.chain_clone import _clone_sqlite_file


def test_clone_sqlite_db_copies_rows():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.db")
        dst = os.path.join(tmp, "dst.db")
        conn = sqlite3.connect(src)
        conn.execute("CREATE TABLE blocks (height INTEGER, hash TEXT)")
        conn.execute("INSERT INTO blocks VALUES (0, 'genesis')")
        conn.execute("INSERT INTO blocks VALUES (1, 'block1')")
        conn.commit()
        conn.close()

        _clone_sqlite_file(src, dst)

        out = sqlite3.connect(dst)
        rows = out.execute("SELECT height, hash FROM blocks ORDER BY height").fetchall()
        out.close()
        assert rows == [(0, "genesis"), (1, "block1")]
