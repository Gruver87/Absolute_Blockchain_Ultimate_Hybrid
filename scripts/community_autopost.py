#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Community autopost for Absolute Blockchain Ultimate.

Modes:
  scheduled  — rotation post every run (GitHub cron: every 3 days)
  release    — post only when new commits since last release post
  dry-run    — print message, do not send

Env:
  TELEGRAM_BOT_TOKEN       — required to send
  TELEGRAM_CHANNEL_ID      — channel or group chat id (e.g. -1001234567890)
  DISCORD_WEBHOOK_URL      — optional second channel
  AUTOPOST_REPO_URL        — default GitHub repo link
  AUTOPOST_STATE_PATH      — default data/community_autopost_state.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPO = "https://github.com/Gruver87/absolute-blockchain-ultimate"
DEFAULT_STATE = ROOT / "data" / "community_autopost_state.json"

# Rotating community posts (RU + honest disclaimer)
ROTATION_POSTS: List[str] = [
    """🔗 <b>Absolute Blockchain Ultimate</b> — учебный блокчейн на Python

🟢 Одна нода: REST :8080, RPC :8545, Explorer, P2P
🟢 PoS-модули, SQLite, токеномика ABS (max 221M)
🟢 Docker devnet: 2 узла, P2P sync проверен

⚠️ Это <b>не production</b> — для обучения и экспериментов.

⭐ Star · 🍴 Fork · 🧪 Локальный запуск:
{repo}

#blockchain #opensource #python #devnet #ABS""",

    """📡 <b>Absolute Devnet</b> — два узла за одну команду

<code>docker_devnet.ps1 -RustBridge</code>
или <code>start_two_nodes.ps1 -RustBridge</code>

✅ P2P gossip + fast-sync
✅ state_root verify, reorg replay
✅ api_wave 45 — L2 dashboard, oracles, bridge

Честная документация: README + CHANGELOG
{repo}

#P2P #blockchain #devnet""",

    """🧪 <b>Wave 37–45</b> — что уже в коде (честно):

• Oracle registry (SQLite) + bridge L1 queue
• Lightning / Plasma / Crypto Will — persistence + L1 effects
• WASM VM, AI agents, MEV history
• Reorg predictor + <code>/l2/status</code>

Проверка: <code>GET /status</code> → <code>api_wave</code>

{repo}
#web3 #learning #blockchain""",

    """💎 Токеномика <b>ABS</b> (учебная модель)

Max supply: <b>221 000 000 ABS</b>
Founder D.U.P. (Uladzimir Dabranski): 17.4%
Burn 2% · pool locks · block rewards

<code>GET /tokenomics</code> · <code>GET /founder</code>

Проект открыт: MIT, pytest 195+ tests
{repo}

#tokenomics #ABS #opensource""",

    """🚀 Ищем контрибьюторов в учебный блокчейн!

Идеи для PR:
• консенсус / P2P / EVM
• тесты, документация, Explorer UI
• bridge relayer, L2 modules

Не для реальных денег — для портфолио и обучения.

{repo}
#opensource #contributors #blockchain""",

    """🖥 <b>Explorer + 256 REST routes</b>

http://localhost:8080 — 32 вкладки UI
/docs — OpenAPI

Bridge · NFT · Sharding · ZK · Lightning · Plasma
Всё в одном <code>python main.py</code>

{repo}
#API #explorer #blockchain""",
]


def _read_api_wave() -> Optional[int]:
    changelog = ROOT / "CHANGELOG.md"
    if not changelog.exists():
        return None
    for line in changelog.read_text(encoding="utf-8", errors="replace").splitlines():
        if "api_wave" in line.lower() and "=" in line:
            try:
                return int(line.split("=")[-1].strip().split()[0])
            except ValueError:
                pass
    readme = ROOT / "README.md"
    if readme.exists():
        for line in readme.read_text(encoding="utf-8", errors="replace").splitlines():
            if "API Wave" in line and "45" in line:
                return 45
    return None


def _git_log(since_sha: str, max_count: int = 8) -> List[Dict[str, str]]:
    fmt = "%H|%s|%an"
    args = ["git", "log", f"--max-count={max_count}", f"--pretty=format:{fmt}"]
    if since_sha:
        args.insert(2, f"{since_sha}..HEAD")
    try:
        out = subprocess.check_output(args, cwd=ROOT, text=True, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    rows = []
    for line in out.strip().splitlines():
        if "|" not in line:
            continue
        sha, subject, author = line.split("|", 2)
        rows.append({"sha": sha[:7], "subject": subject.strip(), "author": author.strip()})
    return rows


def _current_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def load_state(path: Path) -> Dict[str, Any]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_state(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_scheduled_message(repo_url: str) -> str:
    day_index = datetime.now(timezone.utc).timetuple().tm_yday
    template = ROTATION_POSTS[day_index % len(ROTATION_POSTS)]
    wave = _read_api_wave()
    extra = f"\n\n📌 API Wave: <b>{wave}</b>" if wave else ""
    return template.format(repo=repo_url) + extra


def build_release_message(repo_url: str, commits: List[Dict[str, str]]) -> str:
    wave = _read_api_wave()
    lines = [
        "🆕 <b>Absolute Blockchain — обновление</b>",
        "",
        f"Свежие коммиты в репозитории ({len(commits)}):",
    ]
    for c in commits[:6]:
        lines.append(f"• <code>{c['sha']}</code> {c['subject']}")
    if wave:
        lines.append("")
        lines.append(f"📌 API Wave: <b>{wave}</b>")
    lines.extend([
        "",
        "⚠️ Учебный проект, не production mainnet.",
        "",
        f"🔗 {repo_url}",
        "",
        "#blockchain #update #opensource #ABS",
    ])
    return "\n".join(lines)


def post_telegram(token: str, chat_id: str, text: str, dry_run: bool) -> bool:
    if dry_run:
        print("[dry-run] Telegram:", chat_id)
        print(text)
        return True
    if not token or not chat_id:
        print("[autopost] TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID missing", file=sys.stderr)
        return False
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
            if not body.get("ok"):
                print(f"[autopost] Telegram error: {body}", file=sys.stderr)
                return False
            return True
    except Exception as e:
        print(f"[autopost] Telegram failed: {e}", file=sys.stderr)
        return False


def post_discord(webhook_url: str, text: str, dry_run: bool) -> bool:
    # Strip HTML for Discord
    plain = (
        text.replace("<b>", "**").replace("</b>", "**")
        .replace("<code>", "`").replace("</code>", "`")
    )
    if dry_run:
        print("[dry-run] Discord webhook")
        print(plain)
        return True
    if not webhook_url:
        return True
    payload = json.dumps({"content": plain[:2000]}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return 200 <= resp.status < 300
    except Exception as e:
        print(f"[autopost] Discord failed: {e}", file=sys.stderr)
        return False


def run_scheduled(state_path: Path, repo_url: str, dry_run: bool) -> Tuple[bool, str]:
    state = load_state(state_path)
    now = datetime.now(timezone.utc).isoformat()
    last = state.get("last_scheduled_at")
    if last and not dry_run:
        try:
            last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
            delta = datetime.now(timezone.utc) - last_dt
            if delta.total_seconds() < 60 * 60 * 20:  # guard duplicate CI runs
                return False, "scheduled skipped (too soon)"
        except Exception:
            pass
    msg = build_scheduled_message(repo_url)
    ok = _send_all(msg, dry_run)
    if ok and not dry_run:
        state["last_scheduled_at"] = now
        save_state(state_path, state)
    return ok, "scheduled posted" if ok else "scheduled failed"


def run_release(state_path: Path, repo_url: str, dry_run: bool) -> Tuple[bool, str]:
    skip_msg = os.environ.get("AUTOPOST_SKIP", "").lower() in ("1", "true", "yes")
    commit_msg = os.environ.get("GITHUB_COMMIT_MESSAGE", "")
    if skip_msg or "[skip community]" in commit_msg.lower():
        return False, "release skipped ([skip community])"
    state = load_state(state_path)
    head = _current_head()
    last_sha = state.get("last_release_sha", "")
    if head and head == last_sha:
        return False, "release skipped (no new commits)"
    commits = _git_log(last_sha)
    if not commits:
        return False, "release skipped (empty git log)"
    # Skip trivial doc-only if single commit and only .md
    if len(commits) == 1 and commits[0]["subject"].lower().startswith("docs:"):
        return False, "release skipped (docs-only)"
    msg = build_release_message(repo_url, commits)
    ok = _send_all(msg, dry_run)
    if ok and not dry_run and head:
        state["last_release_sha"] = head
        state["last_release_at"] = datetime.now(timezone.utc).isoformat()
        save_state(state_path, state)
    return ok, "release posted" if ok else "release failed"


def _send_all(msg: str, dry_run: bool) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    channel = os.environ.get("TELEGRAM_CHANNEL_ID", "")
    discord = os.environ.get("DISCORD_WEBHOOK_URL", "")
    tg_ok = post_telegram(token, channel, msg, dry_run) if (token and channel) or dry_run else False
    dc_ok = post_discord(discord, msg, dry_run) if discord or dry_run else True
    if not token and not channel and not discord and not dry_run:
        print("[autopost] No channels configured", file=sys.stderr)
        return False
    return tg_ok or dc_ok or (dry_run and True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Community autopost for Absolute Blockchain")
    parser.add_argument(
        "--mode",
        choices=("scheduled", "release", "both"),
        default="scheduled",
        help="scheduled=rotation, release=on new commits, both=try both",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print only, do not send")
    parser.add_argument("--repo-url", default=os.environ.get("AUTOPOST_REPO_URL", DEFAULT_REPO))
    parser.add_argument(
        "--state-path",
        default=os.environ.get("AUTOPOST_STATE_PATH", str(DEFAULT_STATE)),
    )
    args = parser.parse_args()
    state_path = Path(args.state_path)

    results = []
    if args.mode in ("scheduled", "both"):
        ok, note = run_scheduled(state_path, args.repo_url, args.dry_run)
        results.append(f"scheduled: {note} (ok={ok})")
    if args.mode in ("release", "both"):
        ok, note = run_release(state_path, args.repo_url, args.dry_run)
        results.append(f"release: {note} (ok={ok})")

    for r in results:
        print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
