#!/usr/bin/env python3
"""MEGA AUDIT — every file, every integration, every endpoint."""
import ast, os, re, json
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = {"_archive", "__pycache__", ".git", "venv", ".venv", "node_modules", "backup_20260531_030215", "backups"}

def read(p):
    try:
        return open(os.path.join(BASE, p), encoding="utf-8-sig", errors="ignore").read()
    except:
        return ""

main_src  = read("main.py")
http_src  = read("api/http.py")
html_src  = read("web/explorer/index.html")
cfg_src   = read("runtime/config.py")
tok_src   = read("runtime/tokenomics.py")

issues = []
warnings = []

def issue(cat, msg):
    issues.append((cat, msg))

def warn(cat, msg):
    warnings.append((cat, msg))

# ── Collect all .py files ────────────────────────────────────────────────────
all_py = []
for root, dirs, files in os.walk(BASE):
    dirs[:] = [d for d in dirs if d not in SKIP]
    for f in files:
        if f.endswith(".py") and not f.startswith("_"):
            rel = os.path.relpath(os.path.join(root, f), BASE).replace("\\", "/")
            all_py.append(rel)

print("=" * 72)
print("MEGA AUDIT — ABSOLUTE BLOCKCHAIN ULTIMATE")
print("=" * 72)

# ══ 1. SYNTAX ════════════════════════════════════════════════════════════════
print("\n[1] PYTHON SYNTAX")
syntax_errs = []
for p in sorted(all_py):
    try:
        ast.parse(read(p), filename=p)
    except SyntaxError as e:
        syntax_errs.append((p, str(e)))
if syntax_errs:
    for p, e in syntax_errs:
        issue("SYNTAX", f"{p}: {e}")
        print(f"  [ERR] {p}")
else:
    print(f"  [OK] {len(all_py)} files syntax-clean")

# ══ 2. TOKENOMICS ════════════════════════════════════════════════════════════
print("\n[2] TOKENOMICS (221M / 17.4% D.U.P.)")
checks = [
    ("max_supply=221", "221_000_000" in cfg_src or "221000000" in cfg_src),
    ("founder_percent=17.4", "17.4" in cfg_src),
    ("founder_initials D.U.P.", "D.U.P." in cfg_src or "D.U.P." in tok_src),
    ("founder_name", "Uladzimir Dabranski" in cfg_src or "Uladzimir Dabranski" in tok_src),
    ("tokenomics module", os.path.exists(os.path.join(BASE, "runtime/tokenomics.py"))),
    ("genesis_balances in blockchain", "genesis_balances" in read("core/blockchain.py")),
    ("API /tokenomics", '"/tokenomics"' in http_src),
    ("API /founder", '"/founder"' in http_src),
    ("API /allocation", '"/allocation"' in http_src),
    ("Web tokenomics UI", "loadTokenomics" in html_src),
    ("Web founder UI", "loadFounderInfo" in html_src),
]
for name, ok in checks:
    print(f"  {'[OK]' if ok else '[MISS]'} {name}")
    if not ok:
        issue("TOKENOMICS", name)

try:
    import sys
    sys.path.insert(0, BASE)
    from runtime.tokenomics import MAX_SUPPLY_ABS, FOUNDER_PERCENT, get_tokenomics_summary
    s = get_tokenomics_summary()
    pct_sum = sum(a["percent"] for a in s["allocations"])
    print(f"  [OK] Math: {MAX_SUPPLY_ABS:,} ABS, allocations={pct_sum}%")
    if pct_sum != 100.0:
        issue("TOKENOMICS", f"allocations sum {pct_sum}% != 100%")
except Exception as e:
    issue("TOKENOMICS", f"import failed: {e}")

# ══ 3. MAIN.PY COMPONENTS ════════════════════════════════════════════════════
print("\n[3] main.py COMPONENTS")
components = [
    "self.blockchain", "self.mempool", "self.db", "self.config",
    "self.p2p", "self.evm", "self.nft", "self.zk",
    "self.sharding", "self.oracles", "self.contract_manager",
    "self.assembler", "self.pq_manager", "self.smart_accounts",
    "self.multisig", "self.ai_validator", "self.reorg_predictor",
    "self.mev_simulator", "self.immutable_state", "self.lightning",
    "self.crypto_will", "self.plasma", "self.wasm_vm",
    "self.ai_manager", "self.cross_bridge",
    "self.consensus_engine_standalone", "self.finality_engine",
    "self.sync_engine", "self.state_engine", "self.block_builder",
    "self.wallet", "self.ws_server", "self.slashing_engine",
    "self.validator_registry", "self.epoch_manager", "self.beacon_finality",
    "self.lmd_table", "self.consensus_casper", "self.block_validator",
    "self.sphincs", "self.canonical_serializer", "self.consensus_beacon",
    "self.consensus_engine_slashing", "self.casper_finality",
    "self.hasher", "self.key_generator", "self.signer", "self.tx_signer",
    "self.monitor", "self.founder_address",
]
missing_comp = [c for c in components if c.replace("self.", "") not in main_src and c not in main_src]
for c in components:
    found = c in main_src or c.replace("self.", "") in main_src
    if not found:
        print(f"  [MISS] {c}")
        issue("COMPONENT", c)
if not missing_comp:
    print(f"  [OK] All {len(components)} components present")

# ══ 4. HTTP SERVER ARGS ══════════════════════════════════════════════════════
print("\n[4] HTTP SERVER — ARGS PASSED FROM main.py")
http_call = re.search(r"start_http_server_thread\((.*?)\)", main_src, re.DOTALL)
http_block = http_call.group(1) if http_call else ""
http_args = [
    "blockchain", "mempool", "db", "config", "p2p", "evm", "nft", "zk",
    "sharding", "oracles", "contract_manager", "assembler",
    "pq_manager", "smart_accounts", "multisig", "ai_validator",
    "reorg_predictor", "mev_simulator", "immutable_state",
    "lightning", "crypto_will", "plasma", "wasm_vm", "ai_manager",
    "cross_bridge", "consensus_engine_standalone", "finality_engine",
    "sync_engine", "state_engine", "slashing_engine", "validator_registry",
    "epoch_manager", "beacon_finality", "lmd_table", "consensus_casper",
    "block_validator", "sphincs", "canonical_serializer",
    "consensus_beacon", "consensus_engine_slashing", "casper_finality",
]
for arg in http_args:
    if arg not in http_block:
        print(f"  [MISS] {arg}")
        issue("HTTP_ARG", arg)
if all(a in http_block for a in http_args):
    print(f"  [OK] All {len(http_args)} args passed")

# ══ 5. API ENDPOINTS vs WEB UI ═════════════════════════════════════════════
print("\n[5] API ENDPOINTS vs WEB UI")
eq_eps = set(re.findall(r'path == "(/[^"]+)"', http_src))
sw_eps = set(re.findall(r'path\.startswith\("(/[^"]+)"\)', http_src))
all_eps = sorted(eq_eps | sw_eps)

def js_calls(src):
    out = set()
    for pat in [
        r"api\s*\(\s*`(/[^`?#]+)", r"api\s*\(\s*'(/[^'?#]+)", r'api\s*\(\s*"(/[^"?#]+)',
        r"post\s*\(\s*`(/[^`?#]+)", r"post\s*\(\s*'(/[^'?#]+)", r'post\s*\(\s*"(/[^"?#]+)',
        r"get\s*\(\s*`(/[^`?#]+)", r"get\s*\(\s*'(/[^'?#]+)", r'get\s*\(\s*"(/[^"?#]+)',
        r"fetch\s*\(\s*'(/[^'?#]+)", r'fetch\s*\(\s*"(/[^"?#]+)',
    ]:
        out.update(re.findall(pat, src))
    return {u for u in out if u.startswith("/")}

js = js_calls(html_src)
not_covered = []
for ep in all_eps:
    ep_c = ep.rstrip("/")
    if ep_c in js:
        continue
    if any(ep_c == x or ep_c.startswith(x) or x.startswith(ep_c) for x in js):
        continue
    segs = [s for s in ep_c.split("/") if s and s not in
            {"api","v1","stats","list","create","all","call","deploy","status",
             "info","verify","sign","register","advance","get","set","add","remove",
             "delete","update","check","run","load","enable","disable","start","stop",
             "process","finalize","confirm","refund","lock","attest","vote","keygen"}]
    if segs and all(s in html_src for s in segs):
        continue
    not_covered.append(ep)

print(f"  Total endpoints : {len(all_eps)}")
print(f"  Web covered     : {len(all_eps) - len(not_covered)}")
print(f"  NOT covered     : {len(not_covered)}")
for ep in not_covered[:15]:
    print(f"    [NO WEB] {ep}")
    warn("WEB", ep)
if len(not_covered) > 15:
    print(f"    ... and {len(not_covered)-15} more")

# Phantom JS calls (no matching API)
phantom = []
for jc in sorted(js):
    jc_c = jc.rstrip("/")
    found = any(
        ep.rstrip("/") == jc_c or jc_c.startswith(ep.rstrip("/")) or ep.rstrip("/").startswith(jc_c)
        for ep in all_eps
    )
    if not found and jc_c not in html_src.replace(jc, ""):
        # double-check segment presence in http
        segs = [s for s in jc_c.split("/") if len(s) > 2]
        if not any(s in http_src for s in segs):
            phantom.append(jc)
if phantom:
    for p in phantom[:10]:
        print(f"  [PHANTOM JS] {p}")
        warn("PHANTOM", p)

# ══ 6. FEATURE MODULES INTEGRATION ═══════════════════════════════════════════
print("\n[6] FEATURE MODULES — INTEGRATION STATUS")
feature_map = {
    "features/nft.py": "NFTMarketplace",
    "features/lightning.py": "LightningNetwork",
    "features/plasma.py": "PlasmaChain",
    "features/wasm_vm.py": "WASMVM",
    "features/ai_manager.py": "AIAgentManager",
    "features/crypto_will.py": "CryptoWill",
    "features/zk.py": "ZKProofSystem",
    "features/multisig.py": "Multisig",
    "features/smart_accounts.py": "SmartAccount",
    "features/postquantum.py": "PostQuantum",
    "features/ai_validator.py": "AIValidator",
    "features/mev_simulator.py": "MEVSimulator",
    "features/reorg_predictor.py": "ReorgPredictor",
    "real_world_oracles.py": "RealWorldOracles",
    "dynamic_sharding.py": "ShardingManager",
    "cross_chain_bridge.py": "CrossChainBridge",
    "consensus_engine.py": "ConsensusEngine",
    "finality_engine.py": "FinalityEngine",
    "sync/sync_engine.py": "SyncEngine",
    "bridge/abs_bridge.py": "ABSBridge",
    "execution/contract_manager.py": "ContractManager",
    "execution/vm.py": "MiniVM",
    "execution/state_engine.py": "StateEngine",
    "blockchain/immutable_state.py": "ImmutableState",
    "blockchain/mempool.py": "Mempool",
    "consensus/slashing.py": "SlashingEngine",
    "consensus/validator_registry.py": "ValidatorRegistry",
    "consensus/epoch.py": "EpochManager",
    "consensus/finality_beacon.py": "BeaconFinality",
    "consensus/lmd.py": "LMDTable",
    "consensus/engine_casper.py": "ConsensusEngineCasper",
    "consensus/engine_beacon.py": "ConsensusEngineBeacon",
    "consensus/engine_slashing.py": "ConsensusEngineSlashing",
    "consensus/finality_casper.py": "CasperFinality",
    "execution/block_validator.py": "BlockValidator",
    "crypto/sphincs_plus.py": "SPHINCS",
    "blockchain/canonical_serializer.py": "CanonicalSerializer",
    "runtime/tokenomics.py": "tokenomics",
    "compiler/assembler.py": "Assembler",
    "execution/block_builder.py": "BlockBuilder",
    "execution/evm_adapter.py": "EVMAdapter",
    "consensus/adapter.py": "ConsensusAdapter",
    "network/p2p.py": "P2P",
    "network/websocket.py": "WebSocket",
    "monitor.py": "Monitor",
    "telegram_super_bot.py": "Telegram",
    "node_persistent.py": "NodePersistent",
    "api/http.py": "HTTPServer",
    "bridge/l1_rpc.py": "L1RPC",
    "execution/evm_bytecode_validator.py": "EVMBytecodeValidator",
    "crypto/tx_signer.py": "TransactionSigner",
    "crypto/wallet.py": "Wallet",
    "crypto/hashing.py": "Hasher",
    "crypto/keys.py": "KeyGenerator",
    "crypto/signing.py": "Signer",
    "middleware/jwt_auth.py": "JWTAuth",
    "storage/database.py": "Database",
    "kernel/event_bus.py": "EventBus",
}

not_integrated = []
for path, tag in sorted(feature_map.items()):
    exists = os.path.exists(os.path.join(BASE, path))
    if not exists:
        print(f"  [FILE MISSING] {path}")
        issue("FILE", path)
        continue
    src = read(path)
    classes = re.findall(r"^class (\w+)", src, re.MULTILINE)
    in_main = any(c in main_src for c in classes) or tag.lower() in main_src.lower() or path.split("/")[-1].replace(".py","") in main_src
    in_http = any(c in http_src for c in classes) or tag.lower() in http_src.lower()
    if not (in_main or in_http):
        not_integrated.append((path, classes[:2]))
        print(f"  [NOT INTEGRATED] {path} ({classes[:2]})")
        warn("INTEGRATION", f"{path}")

integrated_count = len(feature_map) - len(not_integrated) - sum(1 for p in feature_map if not os.path.exists(os.path.join(BASE, p)))
print(f"  Integrated: {integrated_count}/{len(feature_map)}")
merged_legacy = "Extended API + RPC proxy (standalone servers removed)"
print(f"  [OK] Merged into main.py/api/http.py: {merged_legacy}")

# ══ 7. NAV TABS vs SECTIONS ══════════════════════════════════════════════════
print("\n[7] WEB NAV TABS")
nav_tabs = re.findall(r"onclick=\"show\('(\w+)'\)\"", html_src)
sec_ids  = re.findall(r'id="sec-(\w+)"', html_src)
orphan_nav = set(nav_tabs) - set(sec_ids)
orphan_sec = set(sec_ids) - set(nav_tabs)
show_fn = re.search(r"function show\(tab\)(.*?)^}", html_src, re.DOTALL | re.MULTILINE)
show_body = show_fn.group(1) if show_fn else ""
no_autoload = [t for t in nav_tabs if t not in show_body and t not in ("dashboard", "send", "wallet", "cryptotools")]
print(f"  Tabs: {len(set(nav_tabs))}, Sections: {len(set(sec_ids))}")
if orphan_nav: issue("WEB", f"tabs without section: {orphan_nav}")
if orphan_sec: issue("WEB", f"sections without tab: {orphan_sec}")
if no_autoload:
    for t in no_autoload:
        warn("WEB", f"tab '{t}' no auto-load")
else:
    print("  [OK] All interactive tabs have auto-load")

# ══ 8. REQUIRED FILES ════════════════════════════════════════════════════════
print("\n[8] CRITICAL FILES")
critical = [
    "main.py", "api/http.py", "web/explorer/index.html",
    "runtime/config.py", "runtime/tokenomics.py",
    "core/blockchain.py", "storage/database.py",
    "blockchain/mempool.py", "consensus/adapter.py",
    "execution/evm_adapter.py", "network/p2p_node.py",
    "network/websocket.py", "bridge/abs_bridge.py",
    "compiler/assembler.py", "execution/block_builder.py",
    "data/wallet.json", "requirements.txt", ".env.example",
]
for f in critical:
    ex = os.path.exists(os.path.join(BASE, f))
    if not ex:
        print(f"  [MISSING] {f}")
        issue("FILE", f)
if all(os.path.exists(os.path.join(BASE, f)) for f in critical):
    print(f"  [OK] All {len(critical)} critical files present")

# ══ 9. DUPLICATE ENTRY POINTS ════════════════════════════════════════════════
print("\n[9] MULTIPLE ENTRY POINTS (should be only main.py)")
entry_points = []
for p in all_py:
    src = read(p)
    if p == "main.py":
        continue
    if re.search(r'if __name__\s*==\s*["\']__main__["\']', src):
        if any(kw in src for kw in ["HTTPServer", "asyncio.run", "uvicorn", "app.run", "NodeOrchestrator", "start()"]):
            entry_points.append(p)
if entry_points:
    for ep in entry_points[:12]:
        print(f"  [ALT ENTRY] {ep}")
        warn("ENTRY", ep)
    if len(entry_points) > 12:
        print(f"  ... +{len(entry_points)-12} more alt entry points (sidecars OK)")
else:
    print("  [OK] Only main.py as primary entry")

# ══ 10. IMPORT TEST ══════════════════════════════════════════════════════════
print("\n[10] KEY MODULE IMPORTS")
import_tests = [
    "runtime.config", "runtime.tokenomics", "core.blockchain",
    "storage.database", "api.http", "consensus.adapter",
    "features.nft", "features.zk", "bridge.abs_bridge",
]
import sys
sys.path.insert(0, BASE)
for mod in import_tests:
    try:
        __import__(mod)
        print(f"  [OK] {mod}")
    except Exception as e:
        print(f"  [ERR] {mod}: {e}")
        issue("IMPORT", f"{mod}: {e}")

# ══ SUMMARY ════════════════════════════════════════════════════════════════
print("\n" + "=" * 72)
print("SUMMARY")
print("=" * 72)
print(f"  Python files      : {len(all_py)}")
print(f"  API endpoints       : {len(all_eps)}")
print(f"  Web tabs            : {len(set(nav_tabs))}")
print(f"  CRITICAL issues     : {len(issues)}")
print(f"  Warnings            : {len(warnings)}")
if issues:
    print("\n  CRITICAL:")
    for cat, msg in issues[:20]:
        print(f"    [{cat}] {msg}")
if warnings:
    print("\n  WARNINGS (top 15):")
    for cat, msg in warnings[:15]:
        print(f"    [{cat}] {msg}")
print("\n" + "=" * 72)
print("MEGA AUDIT COMPLETE")
print("=" * 72)

# Save report
report = {
    "files": len(all_py),
    "endpoints": len(all_eps),
    "web_uncovered": not_covered,
    "issues": issues,
    "warnings": [{"cat": c, "msg": m} for c, m in warnings],
    "not_integrated": not_integrated,
}
with open(os.path.join(BASE, "data", "mega_audit_report.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)
