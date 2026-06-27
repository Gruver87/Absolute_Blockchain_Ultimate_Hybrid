#!/usr/bin/env python3
"""FINAL AUDIT — last pass, nothing missed."""
import os, re, json, py_compile, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = {"_archive", "__pycache__", ".git", "venv", ".venv", "node_modules", "backup_20260531_030215", "backups"}

def read(p):
    try:
        return open(os.path.join(BASE, p), encoding="utf-8-sig", errors="ignore").read()
    except:
        return ""

issues, warnings, passed = [], [], []

def fail(cat, msg):
    issues.append((cat, msg))

def warn(cat, msg):
    warnings.append((cat, msg))

def ok(msg):
    passed.append(msg)

print("=" * 72)
print("FINAL AUDIT — ABSOLUTE BLOCKCHAIN ULTIMATE")
print("=" * 72)

main_src = read("main.py")
http_src = read("api/http.py")
html_src = read("web/explorer/index.html")
bc_src   = read("core/blockchain.py")
tok_src  = read("runtime/tokenomics.py")
pl_src   = read("runtime/pool_locks.py")
lc_src   = read("light/light_client.py")
bh_src   = read("core/block_header.py")

# ── 1. New modules exist ───────────────────────────────────────────────────
print("\n[1] NEW MODULES (last session)")
for f in ["core/block_header.py", "light/light_client.py", "light/__init__.py",
          "runtime/pool_locks.py", "node_persistent.py"]:
    ex = os.path.exists(os.path.join(BASE, f))
    print(f"  {'[OK]' if ex else '[MISS]'} {f}")
    if not ex:
        fail("FILE", f)

# ── 2. Integration wiring ──────────────────────────────────────────────────
print("\n[2] INTEGRATION WIRING")
wiring = [
    ("main.pool_locks", "self.pool_locks" in main_src),
    ("main.light_client", "self.light_client" in main_src),
    ("blockchain.pool_locks", "self.pool_locks" in bc_src),
    ("pool_locks in validate_tx", "pool_locks.is_outgoing_allowed" in bc_src),
    ("pool_locks in apply_tx", "pool_locks.record_outgoing" in bc_src),
    ("http pool_locks attr", "pool_locks = None" in http_src),
    ("http light_client attr", "light_client = None" in http_src),
    ("http /pools/locks", '"/pools/locks"' in http_src),
    ("http /light/stats", '"/light/stats"' in http_src),
    ("http /light/spv/verify", '"/light/spv/verify"' in http_src),
    ("http /merkle/proof", '"/merkle/proof/' in http_src),
    ("main passes pool_locks", "pool_locks=self.pool_locks" in main_src),
    ("main passes light_client", "light_client=self.light_client" in main_src),
    ("epoch boundary release", "on_epoch_boundary" in main_src),
    ("light header sync", "BlockHeader.from_block_dict" in main_src),
    ("Block tx_root", "tx_root" in bc_src),
    ("epoch_size=32 config", "epoch_size" in read("runtime/config.py")),
    ("immutable seed", "seed_from_balances" in read("blockchain/immutable_state.py")),
    ("web loadPoolLocks", "loadPoolLocks" in html_src),
    ("web verifySPV", "verifySPV" in html_src),
    ("web loadLightClient", "loadLightClient" in html_src),
    ("web daoVote", "daoVote" in html_src),
]
for name, cond in wiring:
    print(f"  {'[OK]' if cond else '[MISS]'} {name}")
    if not cond:
        fail("WIRE", name)

# ── 3. Tokenomics math ─────────────────────────────────────────────────────
print("\n[3] TOKENOMICS")
sys.path.insert(0, BASE)
try:
    from runtime.tokenomics import MAX_SUPPLY_ABS, FOUNDER_AMOUNT_ABS, build_allocations, genesis_balances
    pools = build_allocations()
    pct = sum(p.percent for p in pools)
    genesis = genesis_balances()
    founder_amt = genesis.get("0xbeb0962327d6f0ad8de263bd883bb184e88744a2", 0)
    checks = [
        ("MAX_SUPPLY=221M", MAX_SUPPLY_ABS == 221_000_000),
        ("Founder=38,454,000", abs(FOUNDER_AMOUNT_ABS - 38_454_000) < 1),
        ("Allocations=100%", abs(pct - 100.0) < 0.01),
        ("Genesis founder balance", founder_amt == 38454000),
        ("Mining excluded from genesis", "mining_pool" not in genesis),
    ]
    for name, c in checks:
        print(f"  {'[OK]' if c else '[FAIL]'} {name}")
        if not c:
            fail("TOKENOMICS", name)
except Exception as e:
    fail("TOKENOMICS", str(e))
    print(f"  [ERR] {e}")

# ── 4. Pool locks live test ────────────────────────────────────────────────
print("\n[4] POOL LOCKS RUNTIME")
try:
    from runtime.pool_locks import PoolLockManager
    from storage.database import Database
    import tempfile
    tdb = os.path.join(tempfile.gettempdir(), "final_audit_pl.db")
    db = Database(tdb)
    pl = PoolLockManager(db)
    eco = "0xecosystem000000000000000000000000000001"
    stk = "0xstaking0000000000000000000000000000001"
    a1, _ = pl.is_outgoing_allowed(eco, 1, 22_100_000)
    pl.catch_up_epochs(3)
    spend = pl.spendable_balance(stk, 0)
    a2 = spend > 0
    for name, c in [("Ecosystem blocked", not a1), ("Staking releases", a2)]:
        print(f"  {'[OK]' if c else '[FAIL]'} {name}")
        if not c:
            fail("POOL", name)
except Exception as e:
    fail("POOL", str(e))
    print(f"  [ERR] {e}")

# ── 5. Light client runtime ────────────────────────────────────────────────
print("\n[5] LIGHT CLIENT RUNTIME")
try:
    from light.light_client import LightClient
    from core.block_header import FullBlock, BlockHeader
    from crypto.merkle import merkle_root, generate_proof, verify_proof
    lc = LightClient()
    fb = FullBlock.create(1, "0xgen", "val", "0xst", [{"a": 1}, {"b": 2}])
    lc.add_header(fb.header)
    txs = [{"a": 1}, {"b": 2}]
    r = lc.verify_transaction_in_block(1, {"b": 2}, txs)
    print(f"  {'[OK]' if r.get('valid') else '[FAIL]'} SPV verify")
    if not r.get("valid"):
        fail("LIGHT", "SPV verify failed")
    print(f"  [OK] Headers: {lc.get_header_count()}")
except Exception as e:
    fail("LIGHT", str(e))
    print(f"  [ERR] {e}")

# ── 6. Node init smoke test ────────────────────────────────────────────────
print("\n[6] NODE INIT SMOKE")
try:
    from main import NodeOrchestrator
    from runtime.config import Config
    n = NodeOrchestrator(Config())
    smoke = [
        ("blockchain", n.blockchain is not None),
        ("pool_locks", n.pool_locks is not None),
        ("light_client", n.light_client is not None),
        ("epoch_manager", n.epoch_manager is not None),
        ("blockchain.pool_locks linked", n.blockchain.pool_locks is n.pool_locks),
        ("height >= 0", n.blockchain.get_height() >= 0),
    ]
    for name, c in smoke:
        print(f"  {'[OK]' if c else '[FAIL]'} {name}")
        if not c:
            fail("NODE", name)
except Exception as e:
    fail("NODE", str(e))
    print(f"  [ERR] {e}")

# ── 7. Stale values in active code ────────────────────────────────────────
print("\n[7] STALE VALUES (active code only)")
stale_patterns = ["500_000_000", "500000000", "100_000_000", "INITIAL_SUPPLY"]
stale_hits = []
for root, dirs, files in os.walk(BASE):
    dirs[:] = [d for d in dirs if d not in SKIP]
    for f in files:
        if not f.endswith(".py"):
            continue
        rel = os.path.relpath(os.path.join(root, f), BASE).replace("\\", "/")
        if rel.startswith("_") or rel == "scripts/final_audit.py":
            continue
        src = read(rel)
        for pat in stale_patterns:
            if pat in src and "tokenomics" not in rel and rel != "runtime/config.py":
                stale_hits.append(f"{rel}: {pat}")
if stale_hits:
    for h in stale_hits[:5]:
        print(f"  [WARN] {h}")
        warn("STALE", h)
else:
    print("  [OK] No stale supply values in active .py")

# ── 8. Known bugs patterns ─────────────────────────────────────────────────
print("\n[8] KNOWN BUG PATTERNS")
bugs = [
    ("block.index (fixed?)", "block.index" in main_src),
    ("block.previous_hash (fixed?)", "block.previous_hash" in main_src),
]
for name, found in bugs:
    if found:
        print(f"  [WARN] {name} still present")
        warn("BUG", name)
    else:
        print(f"  [OK] {name} absent")

# ── 9. HTTP args parity ────────────────────────────────────────────────────
print("\n[9] HTTP SERVER ARGS")
create_sig = re.search(r"def create_http_server\((.*?)\) ->", http_src, re.DOTALL)
start_call = re.search(r"start_http_server_thread\(\s*self\.blockchain.*?pool_locks=.*?\)", main_src, re.DOTALL)
if create_sig and "pool_locks" in create_sig.group(1) and "light_client" in create_sig.group(1):
    print("  [OK] create_http_server has pool_locks + light_client")
else:
    fail("HTTP", "create_http_server missing new args")
    print("  [MISS] create_http_server args")
if start_call:
    print("  [OK] main.py passes pool_locks + light_client")
else:
    fail("HTTP", "main.py start_http_server missing new args")
    print("  [MISS] main.py http call")

# ── 10. Endpoint ↔ Web cross-check ─────────────────────────────────────────
print("\n[10] ENDPOINT WEB CROSS-CHECK")
new_eps = [
    "/pools/locks", "/pools/dao/status", "/pools/dao/vote",
    "/light/stats", "/light/headers", "/light/sync", "/light/spv/verify",
    "/merkle/proof/",
]
for ep in new_eps:
    in_http = ep in http_src or ep.rstrip("/") in http_src
    in_web = ep.replace("/", "").replace("-", "").lower()[:8] in html_src.lower() or ep in html_src
    # simpler: check api call in html
    web_patterns = {
        "/pools/locks": "loadPoolLocks",
        "/pools/dao/vote": "daoVote",
        "/light/stats": "loadLightClient",
        "/light/sync": "syncLightClient",
        "/light/spv/verify": "verifySPV",
        "/merkle/proof/": "getMerkleProof",
        "/pools/dao/status": "loadPoolLocks",
        "/light/headers": "loadLightClient",
    }
    wp = web_patterns.get(ep, "")
    covered = wp and wp in html_src
    status = "[OK]" if (in_http and covered) else "[GAP]"
    print(f"  {status} {ep} http={in_http} web={covered}")
    if in_http and not covered:
        fail("WEB", f"{ep} not in UI")

# ── SUMMARY ────────────────────────────────────────────────────────────────
report = {
    "passed": len(passed),
    "issues": [{"cat": c, "msg": m} for c, m in issues],
    "warnings": [{"cat": c, "msg": m} for c, m in warnings],
    "critical": len(issues),
}
out = os.path.join(BASE, "data", "final_audit_report.json")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print("\n" + "=" * 72)
print("FINAL SUMMARY")
print("=" * 72)
print(f"  Checks passed (explicit): {len(passed)}")
print(f"  CRITICAL issues        : {len(issues)}")
print(f"  Warnings               : {len(warnings)}")
if issues:
    print("\n  CRITICAL:")
    for c, m in issues:
        print(f"    [{c}] {m}")
if warnings:
    print("\n  WARNINGS:")
    for c, m in warnings[:10]:
        print(f"    [{c}] {m}")
print(f"\n  Report: data/final_audit_report.json")
print("=" * 72)
sys.exit(1 if issues else 0)
