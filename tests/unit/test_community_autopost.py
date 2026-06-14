"""Community autopost message builders."""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

_mod_path = Path(ROOT) / "scripts" / "community_autopost.py"
_spec = importlib.util.spec_from_file_location("community_autopost", _mod_path)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)

build_release_message = _mod.build_release_message
build_scheduled_message = _mod.build_scheduled_message
load_state = _mod.load_state
save_state = _mod.save_state
ROTATION_POSTS = _mod.ROTATION_POSTS


def test_rotation_posts_not_empty():
    assert len(ROTATION_POSTS) >= 3
    msg = build_scheduled_message("https://example.com/repo")
    assert "example.com" in msg
    assert len(msg) > 100


def test_release_message_includes_commits():
    commits = [
        {"sha": "abc1234", "subject": "Wave 45: reorg", "author": "dev"},
        {"sha": "def5678", "subject": "Fix API", "author": "dev"},
    ]
    msg = build_release_message("https://github.com/test/repo", commits)
    assert "abc1234" in msg
    assert "Wave 45" in msg
    assert "github.com" in msg


def test_state_roundtrip():
    tmp = Path(tempfile.mkdtemp()) / "state.json"
    save_state(tmp, {"last_release_sha": "deadbeef"})
    st = load_state(tmp)
    assert st["last_release_sha"] == "deadbeef"
