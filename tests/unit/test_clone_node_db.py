import importlib.util
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "scripts", "clone_node_db.py")
_spec = importlib.util.spec_from_file_location("clone_node_db", SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["clone_node_db"] = _mod
_spec.loader.exec_module(_mod)
clone_sqlite_db = _mod.clone_sqlite_db


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

        clone_sqlite_db(src, dst)

        out = sqlite3.connect(dst)
        rows = out.execute("SELECT height, hash FROM blocks ORDER BY height").fetchall()
        out.close()
        assert rows == [(0, "genesis"), (1, "block1")]
