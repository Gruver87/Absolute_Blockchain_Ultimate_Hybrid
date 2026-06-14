#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cross-platform two-node P2P smoke test.

Modes (default: auto):
  auto   — if :8080/:8081 are up, verify running devnet; else spawn isolated CI nodes
  devnet — verify already running nodes (start_two_nodes.ps1 → :8080 / :8081)
  ci     — spawn temporary nodes on :15080 / :15081 (GitHub Actions, no devnet needed)

After start_two_nodes.ps1 use either:
  .\\scripts\\verify_p2p.ps1
  python scripts/verify_p2p_ci.py
  python scripts/verify_p2p_ci.py --mode devnet
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEVNET_URL1 = "http://127.0.0.1:8080"
DEVNET_URL2 = "http://127.0.0.1:8081"
DEVNET_URL3 = "http://127.0.0.1:8082"
DEVNET_URL4 = "http://127.0.0.1:8083"
DEVNET_URL5 = "http://127.0.0.1:8084"


def _api(url: str, timeout: float = 10) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _probe_health(base_url: str, timeout: float = 2) -> bool:
    try:
        _api(f"{base_url}/health/live", timeout=timeout)
        return True
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return False


def _wait_health(base_url: str, max_sec: int = 120) -> bool:
    for _ in range(max_sec // 3):
        if _probe_health(base_url, timeout=5):
            return True
        time.sleep(3)
    return False


def _post_json(base_url: str, path: str, body: dict | None = None, timeout: float = 15) -> dict:
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _trigger_catchup(url1: str, url2: str, s1: dict, s2: dict) -> None:
    """Schedule P2P catch-up on the lagging node."""
    h1 = int(s1.get("height", 0) or 0)
    h2 = int(s2.get("height", 0) or 0)
    try:
        if h2 < h1:
            _post_json(url2, "/sync/fast-sync")
        elif h1 < h2:
            _post_json(url1, "/sync/fast-sync")
    except Exception:
        pass


def _trigger_reconcile(url1: str, url2: str) -> None:
    """Ask both nodes to align forks and state roots."""
    for url in (url1, url2):
        try:
            _post_json(url, "/sync/reconcile")
            _post_json(url, "/sync/fast-sync")
        except Exception:
            pass


def _mempool_has_tx(base_url: str, tx_hash: str) -> bool:
    try:
        mp = _api(f"{base_url}/mempool")
        txs = mp.get("transactions") or []
        for row in txs:
            h = row.get("hash") or row.get("tx_hash") or ""
            if h == tx_hash:
                return True
    except Exception:
        pass
    return False


def _ensure_signer_funded(url1: str) -> None:
    """Top up dev signer via faucet when balance too low for propagation test."""
    try:
        ws = _api(f"{url1}/wallet/status")
        addr = ws.get("signing_address") or ws.get("address") or ""
        bal = float(ws.get("balance", 0) or 0)
        if addr and bal < 1.0:
            _post_json(url1, "/devnet/faucet", {"address": addr, "amount": 100})
    except Exception:
        pass


def _block_has_tx(base_url: str, tx_hash: str, height: int) -> bool:
    try:
        blk = _api(f"{base_url}/block/{height}", timeout=5)
        for row in blk.get("transactions") or []:
            h = row.get("hash") or row.get("tx_hash") or ""
            if h == tx_hash:
                return True
    except Exception:
        pass
    return False


def _peer_saw_tx(base_url: str, tx_hash: str, height_hint: int = 0) -> bool:
    """Mempool gossip, trace, or same-height block inclusion on this node."""
    if _mempool_has_tx(base_url, tx_hash):
        return True
    try:
        trace = _api(f"{base_url}/tx/trace/{tx_hash}", timeout=5)
        status = trace.get("status", "")
        if status in ("mempool", "confirmed", "propagated"):
            return True
        stages = {e.get("stage") for e in trace.get("events", [])}
        if stages & {"mempool", "p2p_received", "p2p_gossip", "block_included"}:
            return True
    except Exception:
        pass
    if height_hint > 0 and _block_has_tx(base_url, tx_hash, height_hint):
        return True
    return False


def _unique_recipient(salt: str = "") -> str:
    """Unique to-address so repeated verify runs do not hit 'already in mempool'."""
    seed = f"abs-p2p-verify-{time.time_ns()}-{salt}-{os.getpid()}"
    return "0x" + hashlib.sha256(seed.encode()).hexdigest()[:40]


def _send_propagation_tx(url1: str, attempt: int = 0) -> dict:
    """POST /tx/send with auto_sign; retries with fresh recipient on duplicate mempool."""
    _ensure_signer_funded(url1)
    last_exc: Exception | None = None
    for i in range(4):
        recipient = _unique_recipient(f"{attempt}-{i}")
        body = {"auto_sign": True, "to": recipient, "value": 0.01, "gas": 21000}
        try:
            return _post_json(url1, "/tx/send", body, timeout=20)
        except Exception as exc:
            last_exc = exc
            msg = str(exc).lower()
            if "already in mempool" in msg or "500" in msg:
                time.sleep(0.2)
                continue
            raise
    if last_exc:
        raise last_exc
    raise RuntimeError("tx/send failed after retries")


def _verify_tx_propagation_multi(url1: str, target_urls: list[str], s1: dict) -> bool:
    """Wave 52: signed tx on node1 must reach all target mempools."""
    wave = int(s1.get("api_wave", 0) or 0)
    if wave < 51:
        print("SKIP: tx propagation (api_wave < 51)")
        return True

    try:
        resp = _send_propagation_tx(url1)
    except Exception as exc:
        print(f"WARN: tx propagation send failed: {exc}")
        return False

    tx_hash = resp.get("tx_hash")
    if not tx_hash:
        print("FAIL: /tx/send returned no tx_hash")
        return False

    height_hint = int(s1.get("height", 0) or 0)
    reached = {url: False for url in target_urls}
    for _ in range(30):
        for url in target_urls:
            if not reached[url] and _peer_saw_tx(url, tx_hash, height_hint):
                reached[url] = True
        if all(reached.values()):
            break
        time.sleep(2)

    confirmed = False
    confirm_height = height_hint
    for _ in range(30):
        try:
            trace = _api(f"{url1}/tx/trace/{tx_hash}")
            if trace.get("status") == "confirmed":
                confirmed = True
                confirm_height = int(trace.get("block_height", 0) or confirm_height)
                break
            stages = [e.get("stage") for e in trace.get("events", [])]
            if "block_included" in stages:
                confirmed = True
                break
        except Exception:
            pass
        time.sleep(3)

    if confirmed and confirm_height > 0:
        for _ in range(25):
            for url in target_urls:
                if reached[url]:
                    continue
                try:
                    st = _api(f"{url}/status", timeout=5)
                    if int(st.get("height", 0) or 0) >= confirm_height:
                        if _block_has_tx(url, tx_hash, confirm_height):
                            reached[url] = True
                            continue
                        try:
                            _api(f"{url}/tx/{tx_hash}", timeout=5)
                            reached[url] = True
                        except Exception:
                            pass
                except Exception:
                    pass
            if all(reached.values()):
                break
            time.sleep(2)

    ok = all(reached.values())
    flags = " ".join(f"n{i+2}={reached[u]}" for i, u in enumerate(target_urls))
    print(
        f"{'OK' if ok else 'FAIL'}: tx propagation hash={tx_hash[:16]}… "
        f"{flags} confirmed={confirmed}"
    )
    return ok


def _verify_tx_propagation(url1: str, url2: str, s1: dict) -> bool:
    """Wave 51: signed tx on node1 must appear in node2 mempool."""
    return _verify_tx_propagation_multi(url1, [url2], s1)


def verify_pair(url1: str, url2: str, wait_sync_sec: int = 240) -> int:
    """Check peers, height sync, attestations on two running nodes."""
    if not _probe_health(url1):
        print(f"FAIL: node1 not reachable at {url1}")
        print("  Start devnet: .\\scripts\\start_two_nodes.ps1")
        return 1
    if not _probe_health(url2):
        print(f"FAIL: node2 not reachable at {url2}")
        print("  Node2 is down. Restart both nodes:")
        print("    .\\scripts\\stop_node.ps1")
        print("    .\\scripts\\start_two_nodes.ps1")
        return 1

    try:
        s1 = _api(f"{url1}/status")
        s2 = _api(f"{url2}/status")
    except Exception as exc:
        print(f"FAIL: cannot read /status: {exc}")
        return 1

    cid1, cid2 = s1.get("chain_id"), s2.get("chain_id")
    if cid1 != cid2:
        print(f"FAIL: chain_id mismatch node1={cid1} node2={cid2}")
        print("  Nodes cannot handshake — stop stray processes and restart:")
        print("    .\\scripts\\stop_node.ps1")
        print("    .\\scripts\\start_two_nodes.ps1")
        print("  Always use --config node.example.json / node2.example.json")
        return 4

    loops = max(20, wait_sync_sec // 3)
    p1 = p2 = {}
    stable_ok = 0
    STABLE_NEED = 3
    MAX_MINING_GAP = 2  # node1 mines while node2 catches up
    for i in range(loops):
        try:
            p1 = _api(f"{url1}/peers")
            p2 = _api(f"{url2}/peers")
            s1 = _api(f"{url1}/status")
            s2 = _api(f"{url2}/status")
            sync1 = _api(f"{url1}/sync/status")
            sync2 = _api(f"{url2}/sync/status")
            gap = abs(int(s1.get("height", 0)) - int(s2.get("height", 0)))
            c1 = int(p1.get("count", 0) or 0)
            c2 = int(p2.get("count", 0) or 0)
            root1 = (sync1.get("state_root") or s1.get("state_root") or "").lower()
            root2 = (sync2.get("state_root") or s2.get("state_root") or "").lower()
            roots_match = bool(root1 and root2 and root1 == root2)
            both_peered = c1 > 0 and c2 > 0

            if both_peered and gap <= MAX_MINING_GAP and roots_match:
                stable_ok += 1
                if stable_ok >= STABLE_NEED:
                    break
            else:
                stable_ok = 0
                if both_peered or c1 > 0 or c2 > 0:
                    if gap > 0:
                        lag_url = url2 if int(s1.get("height", 0)) > int(s2.get("height", 0)) else url1
                        try:
                            _post_json(lag_url, "/sync/reconcile", timeout=120)
                        except Exception:
                            _trigger_catchup(url1, url2, s1, s2)
                    elif not roots_match:
                        _trigger_reconcile(url1, url2)
        except Exception:
            stable_ok = 0
        time.sleep(3)
    else:
        print(f"FAIL: no stable P2P sync after {wait_sync_sec}s")
        print(f"  chain_id={cid1} node1 peers={p1.get('count', '?')} height={s1.get('height', '?')}")
        print(f"  chain_id={cid2} node2 peers={p2.get('count', '?')} height={s2.get('height', '?')}")
        try:
            sync1 = _api(f"{url1}/sync/status")
            sync2 = _api(f"{url2}/sync/status")
            print(
                f"  state_roots node1={str(sync1.get('state_root', ''))[:16]} "
                f"node2={str(sync2.get('state_root', ''))[:16]} "
                f"peer_sync_gap={s1.get('peer_sync_gap', '?')}"
            )
        except Exception:
            pass
        if p1.get("count", 0) > 0 or p2.get("count", 0) > 0:
            print("  Peers linked but heights/state diverged - try:")
            print("    Invoke-RestMethod http://127.0.0.1:8081/sync/reconcile -Method POST -Body '{}' -ContentType 'application/json'")
            print("    Invoke-RestMethod http://127.0.0.1:8081/sync/fast-sync -Method POST -Body '{}' -ContentType 'application/json'")
        print("  Or: .\\scripts\\stop_node.ps1  then  .\\scripts\\docker_devnet.ps1 -RustBridge")
        return 2

    sync1 = _api(f"{url1}/sync/status")
    sync2 = _api(f"{url2}/sync/status")
    att1 = _api(f"{url1}/consensus/attestations")
    gap = abs(int(s1.get("height", 0)) - int(s2.get("height", 0)))
    if gap > 50:
        print(f"FAIL: height gap too large ({gap})")
        return 3

    root1 = (sync1.get("state_root") or s1.get("state_root") or "").lower()
    root2 = (sync2.get("state_root") or s2.get("state_root") or "").lower()
    consistent = sync1.get("state_consistent", True) and sync2.get("state_consistent", True)
    roots_match = bool(root1 and root2 and root1 == root2)

    print(
        f"OK: peers n1={p1.get('count', 0)} n2={p2.get('count', 0)} "
        f"heights {s1.get('height')} / {s2.get('height')} "
        f"nodes {s1.get('node_id', '?')} / {s2.get('node_id', '?')} "
        f"attestations={att1.get('count', 0)} "
        f"state_consistent={consistent} state_roots_match={roots_match}"
    )
    if s1.get("node_id", "").startswith("node-") and not s1.get("node_id", "").startswith("docker-"):
        print("WARN: :8080/:8081 answer local nodes — stop them: .\\scripts\\stop_node.ps1")
    if gap > 0:
        print(f"WARN: height gap {gap} — lagging node still catching up")
        return 6
    if gap == 0 and not roots_match:
        print("WARN: same height but state_root differs — re-run docker_devnet or start_two_nodes.ps1")
        print("  Tip: Invoke-RestMethod http://127.0.0.1:8081/sync/reconcile -Method POST -Body '{}' -ContentType 'application/json'")
        return 5
    if not _verify_tx_propagation(url1, url2, s1):
        return 7
    return verify_state_consistency([url1, url2], s1)


def verify_state_consistency(urls: list[str], status: dict) -> int:
    """Wave 54: cross-node state consistency harness."""
    wave = int(status.get("api_wave", 0) or 0)
    if wave < 54:
        print(f"SKIP: state consistency harness (api_wave={wave} < 54)")
        return verify_adversarial(urls[0], status)

    def _run_harness() -> tuple[bool, list[str], list[str]]:
        roots: list[str] = []
        all_ok = True
        failed_nodes: list[str] = []
        for i, url in enumerate(urls, start=1):
            try:
                h = _api(f"{url}/chain/consistency/harness")
            except Exception as exc:
                print(f"FAIL: node{i} harness: {exc}")
                return False, [], [f"node{i}"]
            roots.append(str(h.get("live_state_root") or "").lower())
            if not h.get("harness_healthy"):
                all_ok = False
                failed = h.get("failed_checks") or []
                failed_nodes.append(f"node{i}:{','.join(failed)}")
        roots_match = bool(roots[0] and all(r == roots[0] for r in roots))
        return all_ok and roots_match, roots, failed_nodes

    ok, roots, failed = _run_harness()
    if not ok:
        print("WARN: harness unhealthy — attempting repair on all nodes")
        for url in urls:
            try:
                _post_json(url, "/chain/consistency/repair", timeout=60)
            except Exception:
                pass
        ok, roots, failed = _run_harness()

    if not ok:
        print(f"FAIL: state consistency harness unhealthy ({'; '.join(failed)})")
        if roots:
            print(f"  roots={[r[:16] for r in roots]}")
        return 12

    print(
        f"OK: state consistency harness healthy across {len(urls)} nodes "
        f"root={roots[0][:16] if roots else '?'}…"
    )
    return verify_validators_set(urls[0], status)


def verify_validators_set(url1: str, status: dict) -> int:
    """Wave 55: 5-validator manifest health on hub node."""
    wave = int(status.get("api_wave", 0) or 0)
    if wave < 55:
        return verify_adversarial(url1, status)
    try:
        val = _api(f"{url1}/testnet/validators")
    except Exception as exc:
        print(f"FAIL: /testnet/validators: {exc}")
        return 15
    if not val.get("validators_healthy"):
        print(
            f"FAIL: validators unhealthy registered={val.get('registered_count')} "
            f"expected={val.get('expected_validators')}"
        )
        return 15
    rot = bool(val.get("rotation_observed"))
    print(
        f"OK: validators active={val.get('active_count')} "
        f"distinct_proposers={val.get('distinct_proposers')} rotation_observed={rot}"
    )
    if not rot and int(status.get("height", 0) or 0) >= 12:
        print("WARN: proposer rotation not observed yet (chain may be young)")
    return verify_adversarial(url1, status)


def verify_n_nodes(urls: list[str], wait_sync_sec: int = 300) -> int:
    """Multi-node sync, mesh (hub), tx propagation, consistency, validators."""
    url1 = urls[0]
    for i, url in enumerate(urls, start=1):
        if not _probe_health(url):
            print(f"FAIL: node{i} not reachable at {url}")
            return 1

    try:
        statuses = [_api(f"{u}/status") for u in urls]
    except Exception as exc:
        print(f"FAIL: cannot read /status: {exc}")
        return 1

    cid = statuses[0].get("chain_id")
    for i, st in enumerate(statuses[1:], start=2):
        if st.get("chain_id") != cid:
            print(f"FAIL: chain_id mismatch node1={cid} node{i}={st.get('chain_id')}")
            return 4

    loops = max(20, wait_sync_sec // 3)
    stable_ok = 0
    STABLE_NEED = 3
    MAX_MINING_GAP = 2
    p_counts = [0] * len(urls)
    for _ in range(loops):
        try:
            statuses = [_api(f"{u}/status") for u in urls]
            peers = [_api(f"{u}/peers") for u in urls]
            syncs = [_api(f"{u}/sync/status") for u in urls]
            heights = [int(s.get("height", 0) or 0) for s in statuses]
            max_h = max(heights)
            gap = max_h - min(heights)
            p_counts = [int(p.get("count", 0) or 0) for p in peers]
            roots = [
                (syncs[i].get("state_root") or statuses[i].get("state_root") or "").lower()
                for i in range(len(urls))
            ]
            roots_match = bool(roots[0] and all(r == roots[0] for r in roots))
            all_peered = all(c > 0 for c in p_counts)
            if all_peered and gap <= MAX_MINING_GAP and roots_match:
                stable_ok += 1
                if stable_ok >= STABLE_NEED:
                    break
            else:
                stable_ok = 0
                for url in urls:
                    try:
                        st = _api(f"{url}/status")
                        if int(st.get("height", 0) or 0) < max_h:
                            _post_json(url, "/sync/reconcile", timeout=120)
                            _post_json(url, "/sync/fast-sync", timeout=120)
                    except Exception:
                        pass
        except Exception:
            stable_ok = 0
        time.sleep(3)
    else:
        print(f"FAIL: no stable {len(urls)}-node sync after {wait_sync_sec}s")
        for i, (st, pc) in enumerate(zip(statuses, p_counts), start=1):
            print(f"  node{i} peers={pc} height={st.get('height', '?')}")
        return 2

    try:
        mesh = _api(f"{url1}/testnet/mesh")
        mesh_ok = bool(mesh.get("mesh_healthy"))
        print(
            f"OK: {len(urls)}-node mesh peer_count={mesh.get('peer_count')} "
            f"mesh_healthy={mesh_ok} heights={' / '.join(str(s.get('height')) for s in statuses)}"
        )
        if len(urls) >= 3 and not mesh_ok and p_counts[0] < 2:
            return 9
    except Exception:
        print(
            f"OK: {len(urls)}-node heights {' / '.join(str(s.get('height')) for s in statuses)}"
        )

    if not _verify_tx_propagation_multi(url1, urls[1:], statuses[0]):
        return 7
    return verify_state_consistency(urls, statuses[0])


def verify_triple(url1: str, url2: str, url3: str, wait_sync_sec: int = 300) -> int:
    return verify_n_nodes([url1, url2, url3], wait_sync_sec)


def verify_quintuple(
    url1: str, url2: str, url3: str, url4: str, url5: str, wait_sync_sec: int = 360
) -> int:
    return verify_n_nodes([url1, url2, url3, url4, url5], wait_sync_sec)


def verify_adversarial(url1: str, status: dict) -> int:
    """Wave 53: fork-status API, reconcile, double-vote slashing."""
    wave = int(status.get("api_wave", 0) or 0)
    if wave < 53:
        print(f"SKIP: adversarial checks (api_wave={wave} < 53)")
        return 0

    try:
        fork = _api(f"{url1}/testnet/fork-status")
    except Exception as exc:
        print(f"FAIL: /testnet/fork-status: {exc}")
        return 10

    if fork.get("same_height_divergent_heads"):
        print("WARN: divergent heads at same height — triggering reconcile")
        try:
            _post_json(url1, "/sync/reconcile", timeout=120)
            _post_json(url1, "/sync/fast-sync", timeout=120)
            fork = _api(f"{url1}/testnet/fork-status")
        except Exception:
            pass

    healthy = bool(fork.get("consensus_healthy"))
    print(
        f"{'OK' if healthy else 'WARN'}: fork-status "
        f"consensus_healthy={healthy} fork_detected={fork.get('fork_detected')} "
        f"gap={fork.get('max_peer_height_gap')} slash_events={fork.get('slash_events_count')}"
    )

    test_val = "0x" + "a1" * 20
    slot = 900_001
    try:
        _post_json(
            url1,
            "/slashing/add-validator",
            {"validator_address": test_val, "stake": 1000},
        )
        r1 = _post_json(
            url1,
            "/slashing/record-vote",
            {"validator": test_val, "block_hash": "0x" + "11" * 32, "epoch": slot},
        )
        r2 = _post_json(
            url1,
            "/slashing/record-vote",
            {"validator": test_val, "block_hash": "0x" + "22" * 32, "epoch": slot},
        )
        slashed = bool(r1.get("slashed")) or bool(r2.get("slashed"))
        events = _api(f"{url1}/slashing/events?limit=10")
        ev_count = int(events.get("count", 0) or 0)
        if not slashed and ev_count == 0:
            print("FAIL: double-vote did not produce slash event")
            return 11
        print(f"OK: slashing double-vote slashed={slashed} events={ev_count}")
    except Exception as exc:
        print(f"FAIL: slashing adversarial test: {exc}")
        return 11

    return 0


def run_ci3_spawn() -> int:
    """Isolated three-node test on high ports (GitHub Actions, no Docker)."""
    tmp = tempfile.mkdtemp(prefix="abs_p2p_ci3_")
    common = {
        "chain_id": 77777,
        "mining_enabled": False,
        "require_signatures": False,
        "verify_peer_state_root": True,
        "state_root_legacy_cutoff_height": 0,
        "monitor_enabled": False,
        "bridge_enabled": False,
        "testnet_expected_peers": 2,
        "block_time": 30,
    }
    nodes = []
    for i, (http_p, p2p_p, rpc_p, ws_p, boot) in enumerate(
        (
            (15080, 15000, 15045, 15066, []),
            (15081, 15001, 15046, 15067, ["127.0.0.1:15000"]),
            (15082, 15002, 15047, 15068, ["127.0.0.1:15000", "127.0.0.1:15001"]),
        ),
        start=1,
    ):
        nodes.append({
            **common,
            "node_id": f"ci-node-{i}",
            "p2p_port": p2p_p,
            "http_port": http_p,
            "rpc_port": rpc_p,
            "ws_port": ws_p,
            "mining_enabled": i == 1,
            "testnet_expected_peers": 2,
            "bootstrap_peers": boot,
            "db_path": os.path.join(tmp, f"node{i}.db"),
            "log_file": os.path.join(tmp, f"node{i}.log"),
        })

    env = os.environ.copy()
    env.pop("TELEGRAM_BOT_TOKEN", None)
    env["MINING_ENABLED"] = ""

    procs = []
    try:
        print(f"CI3 mode: spawning isolated nodes on :15080/:15081/:15082 (tmp={tmp})")
        for ncfg in nodes:
            cfg_path = os.path.join(tmp, f"{ncfg['node_id']}.json")
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(ncfg, f)
            log_path = ncfg["log_file"]
            err_f = open(log_path, "w", encoding="utf-8")
            proc = subprocess.Popen(
                [sys.executable, "main.py", "--config", cfg_path],
                cwd=ROOT,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=err_f,
            )
            procs.append((proc, err_f, log_path))

        urls = [f"http://127.0.0.1:{ncfg['http_port']}" for ncfg in nodes]
        for url, ncfg in zip(urls, nodes):
            if not _wait_health(url, max_sec=240):
                print(f"FAIL: health timeout {url}")
                print(f"  log: {ncfg['log_file']}")
                return 1

        rc = verify_triple(urls[0], urls[1], urls[2], wait_sync_sec=180)
        return rc
    finally:
        for proc, log_f, _ in procs:
            try:
                log_f.close()
            except Exception:
                pass
            proc.terminate()
            try:
                proc.wait(timeout=12)
            except Exception:
                proc.kill()


def run_ci_spawn() -> int:
    """Isolated two-node test on high ports (does not touch devnet :8080)."""
    tmp = tempfile.mkdtemp(prefix="abs_p2p_ci_")
    common = {
        "chain_id": 77777,
        "mining_enabled": False,
        "require_signatures": False,
        "verify_peer_state_root": True,
        "state_root_legacy_cutoff_height": 0,
        "monitor_enabled": False,
        "bridge_enabled": False,
    }
    n1 = {
        **common,
        "node_id": "ci-node-1",
        "p2p_port": 15000,
        "http_port": 15080,
        "rpc_port": 15045,
        "ws_port": 15066,
        "mining_enabled": True,
        "bootstrap_peers": [],
        "db_path": os.path.join(tmp, "node1.db"),
        "log_file": os.path.join(tmp, "node1.log"),
    }
    n2 = {
        **common,
        "node_id": "ci-node-2",
        "p2p_port": 15001,
        "http_port": 15081,
        "rpc_port": 15046,
        "ws_port": 15067,
        "bootstrap_peers": ["127.0.0.1:15000"],
        "db_path": os.path.join(tmp, "node2.db"),
        "log_file": os.path.join(tmp, "node2.log"),
    }

    cfg1 = os.path.join(tmp, "node1.json")
    cfg2 = os.path.join(tmp, "node2.json")
    with open(cfg1, "w", encoding="utf-8") as f:
        json.dump(n1, f)
    with open(cfg2, "w", encoding="utf-8") as f:
        json.dump(n2, f)

    env = os.environ.copy()
    env.pop("TELEGRAM_BOT_TOKEN", None)
    env["MINING_ENABLED"] = ""

    log1 = os.path.join(tmp, "node1.stderr.log")
    log2 = os.path.join(tmp, "node2.stderr.log")
    procs = []
    try:
        print(f"CI mode: spawning isolated nodes on :15080 / :15081 (tmp={tmp})")
        with open(log1, "w", encoding="utf-8") as err1:
            procs.append(
                subprocess.Popen(
                    [sys.executable, "main.py", "--config", cfg1],
                    cwd=ROOT,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=err1,
                )
            )
        if not _wait_health("http://127.0.0.1:15080"):
            print("FAIL: node1 health timeout on :15080")
            print(f"  stderr: {log1}")
            return 1

        with open(log2, "w", encoding="utf-8") as err2:
            procs.append(
                subprocess.Popen(
                    [sys.executable, "main.py", "--config", cfg2],
                    cwd=ROOT,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=err2,
                )
            )
        if not _wait_health("http://127.0.0.1:15081"):
            print("FAIL: node2 health timeout on :15081")
            print(f"  stderr: {log2}")
            return 1

        return verify_pair("http://127.0.0.1:15080", "http://127.0.0.1:15081")
    finally:
        for proc in procs:
            proc.terminate()
            try:
                proc.wait(timeout=12)
            except Exception:
                proc.kill()


def main() -> int:
    os.chdir(ROOT)
    parser = argparse.ArgumentParser(description="P2P verification (2-node or 3-node)")
    parser.add_argument(
        "--mode",
        choices=("auto", "devnet", "devnet3", "devnet5", "ci", "ci3", "ci-adversarial"),
        default="auto",
        help="auto; devnet/devnet3/devnet5; ci/ci3",
    )
    parser.add_argument("--url1", default=DEVNET_URL1, help="node1 REST base URL")
    parser.add_argument("--url2", default=DEVNET_URL2, help="node2 REST base URL")
    parser.add_argument("--url3", default=DEVNET_URL3, help="node3 REST base URL")
    parser.add_argument("--url4", default=DEVNET_URL4, help="node4 REST base URL")
    parser.add_argument("--url5", default=DEVNET_URL5, help="node5 REST base URL")
    parser.add_argument(
        "--wait",
        type=int,
        default=240,
        help="seconds to wait for stable P2P sync (devnet mode)",
    )
    args = parser.parse_args()

    mode = args.mode
    if mode == "auto":
        up1 = _probe_health(args.url1)
        up2 = _probe_health(args.url2)
        up3 = _probe_health(args.url3)
        if up1 and up2 and up3:
            mode = "devnet3"
            print(f"Auto: 3-node devnet at {args.url1} {args.url2} {args.url3}")
        elif up1 and up2:
            mode = "devnet"
            print(f"Auto: devnet detected at {args.url1} and {args.url2}")
        elif up1 or up2 or up3:
            print("FAIL: incomplete devnet cluster")
            print(f"  node1 :8080 {'UP' if up1 else 'DOWN'}")
            print(f"  node2 :8081 {'UP' if up2 else 'DOWN'}")
            print(f"  node3 :8082 {'UP' if up3 else 'DOWN'}")
            print("  Fix 2-node: .\\scripts\\docker_devnet.ps1 -RustBridge")
            print("  Fix 3-node: .\\scripts\\docker_devnet_3node.ps1")
            return 1
        else:
            mode = "ci"
            print("Auto: no devnet on :8080/:8081 — running isolated CI test (--mode ci)")

    if mode == "devnet5":
        print(f"Devnet5 mode: checking {args.url1} .. {args.url5}")
        return verify_quintuple(
            args.url1, args.url2, args.url3, args.url4, args.url5, wait_sync_sec=args.wait
        )

    if mode == "devnet3":
        print(f"Devnet3 mode: checking {args.url1} {args.url2} {args.url3}")
        return verify_triple(args.url1, args.url2, args.url3, wait_sync_sec=args.wait)

    if mode == "devnet":
        print(f"Devnet mode: checking {args.url1} and {args.url2}")
        return verify_pair(args.url1, args.url2, wait_sync_sec=args.wait)

    if mode in ("ci3", "ci-adversarial"):
        return run_ci3_spawn()

    return run_ci_spawn()


if __name__ == "__main__":
    sys.exit(main())
