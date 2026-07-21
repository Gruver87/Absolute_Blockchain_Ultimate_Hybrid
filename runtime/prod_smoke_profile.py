#!/usr/bin/env python3
"""Isolated production-profile spawn helpers (CI / E2E smoke)."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Tuple

from runtime.mainnet_constants import MAINNET_V1_CHAIN_ID

ROOT = Path(__file__).resolve().parents[1]

PROD_SMOKE_CHAIN_ID = MAINNET_V1_CHAIN_ID


PROD_SMOKE_HTTP_PORTS = (15180, 15181)
PROD_SMOKE_P2P_PORTS = (15100, 15101)

PROD_MESH3_HTTP_PORTS = (15280, 15281, 15282)
PROD_MESH3_P2P_PORTS = (15200, 15201, 15202)
PROD_MESH3_RPC_PORTS = (15245, 15246, 15247)
PROD_MESH3_WS_PORTS = (15266, 15267, 15268)


def ensure_smoke_ports_free(
    ports: tuple[int, ...] | None = None,
) -> list[int]:
    """Return ports with an active TCP listener on 127.0.0.1 (empty = OK to spawn)."""
    import socket

    check = ports or (*PROD_SMOKE_HTTP_PORTS, *PROD_SMOKE_P2P_PORTS)
    busy: list[int] = []
    for port in check:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        try:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                busy.append(port)
        finally:
            sock.close()
    return busy


def prod_smoke_secret_env() -> Dict[str, str]:
    """Non-placeholder secrets for prod Config.validate() in isolated smoke."""
    jwt_secret = "prod-smoke-jwt-" + ("Q" * 32)
    secrets = {
        "JWT_SECRET": jwt_secret,
        "RPC_API_KEYS": "prod-smoke-rpc-" + ("R" * 32),
        "BRIDGE_ORACLE_SECRET": "prod-smoke-oracle-" + ("S" * 32),
        "ETH_RPC_URL": "https://rpc.example.com",
        "CORS_ORIGINS": "https://explorer.example.com",
        "BRIDGE_PROBE_L1_RPC": "false",
        "ABS_REQUIRE_NATIVE_CRYPTO": "true",
        "DEPLOYMENT_MODE": "prod",
    }
    try:
        import jwt as pyjwt
        import secrets as pysecrets
        import time as pytime

        secrets["PROD_SMOKE_ADMIN_JWT"] = pyjwt.encode(
            {
                "address": "prod-smoke-admin",
                "role": "admin",
                "iat": pytime.time(),
                "exp": pytime.time() + 86400,
                "jti": pysecrets.token_hex(16),
            },
            jwt_secret,
            algorithm="HS256",
        )
    except Exception:
        pass
    return secrets


def apply_prod_smoke_env(base: Dict[str, str] | None = None) -> Dict[str, str]:
    env = dict(base or os.environ)
    env.update(prod_smoke_secret_env())
    env.pop("TELEGRAM_BOT_TOKEN", None)
    # Isolated smoke must not inherit deploy/ceremony pins from the parent shell.
    for key in (
        "VALIDATORS_MANIFEST_PATH",
        "GENESIS_CEREMONY_HASH",
        "GENESIS_STRICT_MAINNET",
    ):
        env.pop(key, None)
    return env


def _write_wallet(data_dir: Path, *, source: Path | None = None) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    wallet = data_dir / "wallet.json"
    if source is not None:
        shutil.copy2(source, wallet)
        return
    if not wallet.is_file():
        from crypto.wallet import Wallet

        w = Wallet()
        wallet.write_text(
            json.dumps(
                {
                    "address": w.address,
                    "public_key": w.public_key,
                    "private_key": w.private_key,
                    "label": "prod-smoke-ci",
                },
                indent=2,
            ),
            encoding="utf-8",
        )


def _shared_smoke_wallet(tmp: Path) -> tuple[Path, str]:
    """One wallet for all smoke nodes so genesis/state_root match across the mesh."""
    shared_dir = tmp / "_shared"
    shared_dir.mkdir(parents=True, exist_ok=True)
    shared_wallet = shared_dir / "wallet.json"
    _write_wallet(shared_dir)
    with open(shared_wallet, encoding="utf-8") as f:
        address = str(json.load(f).get("address", ""))
    return shared_wallet, address


def _wallet_address(data_dir: Path) -> str:
    _write_wallet(data_dir)
    with open(data_dir / "wallet.json", encoding="utf-8") as f:
        return str(json.load(f).get("address", ""))


def _write_smoke_manifest(path: Path, miner_addr: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": 1,
        "description": "Prod smoke isolated validator set (CI only, single proposer)",
        "validators": [
            {
                "index": 1,
                "node_id": "prod-smoke-1",
                "address": miner_addr,
                "public_key": "",
                "mines": True,
                "stake": 5000,
                "shard_id": 0,
            },
        ],
    }
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return str(path)


def native_available() -> bool:
    try:
        from crypto import native as nc
        if not nc.native_available():
            return False
        st = nc.native_crypto_status(required=False)
        return bool(st.get("self_test"))
    except Exception:
        return False


def rocks_engine_available() -> bool:
    try:
        import abs_native  # type: ignore

        return hasattr(abs_native, "RocksEngine")
    except Exception:
        return False


def prod_storage_fields(data_dir: Path) -> Dict[str, Any]:
    """Prod isolated spawn storage: RocksDB when native engine is built."""
    if rocks_engine_available():
        return {
            "db_engine": "rocksdb",
            "rocksdb_sync": "FULL",
            "db_path": str(data_dir / "chainstore"),
            "sqlite_synchronous": "FULL",
        }
    return {
        "db_engine": "sqlite",
        "sqlite_synchronous": "FULL",
        "db_path": str(data_dir / "chain.db"),
    }


def prod_node_config(
    tmp: str,
    *,
    node_id: str,
    http_port: int,
    p2p_port: int,
    rpc_port: int,
    ws_port: int,
    bootstrap_peers: List[str],
    mining_enabled: bool = False,
    bridge_enabled: bool = False,
    validators_manifest_path: str | None = None,
    wallet_source: Path | None = None,
) -> Dict[str, Any]:
    """Build prod-like node JSON for isolated spawn (high ports)."""
    data_dir = Path(tmp) / node_id
    _write_wallet(data_dir, source=wallet_source)
    manifest = validators_manifest_path or str(ROOT / "validators.manifest.example.json")
    return {
        "node_id": node_id,
        "network_name": "Absolute Prod Smoke",
        "chain_id": PROD_SMOKE_CHAIN_ID,
        "deployment_mode": "prod",
        "http_host": "127.0.0.1",
        "rpc_host": "127.0.0.1",
        "ws_host": "127.0.0.1",
        "p2p_host": "127.0.0.1",
        "p2p_port": p2p_port,
        "http_port": http_port,
        "rpc_port": rpc_port,
        "ws_port": ws_port,
        "bootstrap_peers": bootstrap_peers,
        "mining_enabled": mining_enabled,
        "require_signatures": True,
        "require_native_crypto": True,
        "enforce_proposer": True,
        "verify_peer_state_root": True,
        "state_root_strict_p2p": True,
        "state_root_legacy_cutoff_height": 0,
        "monitor_enabled": False,
        "bridge_enabled": bridge_enabled,
        "bridge_mode": "rust",
        "bridge_require_l1_proof": True,
        "bridge_auto_confirm_sec": 0,
        "evm_create2_eip1014": True,
        "evm_require_deploy_salt": True,
        "rpc_api_key_required": True,
        "jwt_enforce_admin": True,
        "require_wallet_file": True,
        "consensus_mode": "unified",
        "feature_zk": False,
        "feature_sharding": False,
        "feature_oracles": False,
        "feature_wasm": False,
        "feature_plasma": False,
        "feature_lightning": False,
        "feature_pq": False,
        "feature_mev": False,
        "feature_ai_agents": False,
        "allow_state_root_rewrite": False,
        "rate_limit_rpm": 120,
        "log_json": False,
        "enable_cors_rpc_proxy": False,
        "cors_origins": ["https://explorer.example.com"],
        "validators_manifest_path": manifest,
        "log_file": str(data_dir / "node.log"),
        **prod_storage_fields(data_dir),
    }


def write_prod_pair_configs(
    tmp: str,
    *,
    bridge_enabled: bool = False,
) -> Tuple[str, str, str, str]:
    """Write node1/node2 prod smoke configs; return (cfg1, cfg2, url1, url2)."""
    root = Path(tmp)
    shared_wallet, miner_addr = _shared_smoke_wallet(root)
    manifest_path = _write_smoke_manifest(
        root / "validators.smoke.json",
        miner_addr,
    )
    n1 = prod_node_config(
        tmp,
        node_id="prod-smoke-1",
        http_port=15180,
        p2p_port=15100,
        rpc_port=15145,
        ws_port=15166,
        bootstrap_peers=[],
        mining_enabled=True,
        bridge_enabled=bridge_enabled,
        validators_manifest_path=manifest_path,
        wallet_source=shared_wallet,
    )
    n2 = prod_node_config(
        tmp,
        node_id="prod-smoke-2",
        http_port=15181,
        p2p_port=15101,
        rpc_port=15146,
        ws_port=15167,
        bootstrap_peers=["127.0.0.1:15100"],
        mining_enabled=False,
        bridge_enabled=bridge_enabled,
        validators_manifest_path=manifest_path,
        wallet_source=shared_wallet,
    )
    cfg1 = os.path.join(tmp, "prod-node1.json")
    cfg2 = os.path.join(tmp, "prod-node2.json")
    with open(cfg1, "w", encoding="utf-8") as f:
        json.dump(n1, f, indent=2)
    with open(cfg2, "w", encoding="utf-8") as f:
        json.dump(n2, f, indent=2)
    return cfg1, cfg2, "http://127.0.0.1:15180", "http://127.0.0.1:15181"


def resolve_ceremony_dir(ceremony_dir: str = "") -> Path:
    """Ceremony dir for prod mesh (explicit path, data/ceremony_keys, or CI dir)."""
    if ceremony_dir:
        cdir = Path(ceremony_dir)
        if not cdir.is_absolute():
            cdir = ROOT / cdir
        return cdir
    for candidate in (ROOT / "data" / "ceremony_keys", ROOT / "data" / "ceremony_keys_ci"):
        if (candidate / "validators.manifest.json").is_file():
            return candidate
    return ROOT / "data" / "ceremony_keys"


def write_prod_mesh3_configs(
    tmp: str,
    ceremony_dir: str = "",
    *,
    bridge_enabled: bool = False,
) -> Tuple[str, str, str, str, str, str]:
    """Three prod nodes with distinct ceremony wallets (ports :15280-15282)."""
    from runtime.validator_loader import manifest_entries

    cdir = resolve_ceremony_dir(ceremony_dir)
    manifest_src = cdir / "validators.manifest.json"
    if not manifest_src.is_file():
        raise FileNotFoundError(f"ceremony manifest missing: {manifest_src}")

    root = Path(tmp)
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "validators.manifest.json"
    shutil.copy2(manifest_src, manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = sorted(manifest_entries(manifest), key=lambda r: int(r.get("index", 0) or 0))[:3]
    if len(rows) < 3:
        raise ValueError(f"ceremony mesh requires 3 validators, found {len(rows)}")

    primary_miner_index = next(
        (int(r.get("index", 0) or 0) for r in rows if bool(r.get("mines", True))),
        int(rows[0].get("index", 1) or 1),
    )
    for row in manifest.get("validators") or []:
        if not isinstance(row, dict):
            continue
        idx = int(row.get("index", 0) or 0)
        row["mines"] = idx == primary_miner_index
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    cfgs: list[str] = []
    urls: list[str] = []
    for i, row in enumerate(rows):
        index = int(row.get("index", 0) or 0)
        wallet_src = cdir / "wallets" / f"validator-{index}.wallet.json"
        if not wallet_src.is_file():
            raise FileNotFoundError(f"ceremony wallet missing: {wallet_src}")
        bootstrap = [f"127.0.0.1:{PROD_MESH3_P2P_PORTS[j]}" for j in range(i)]
        cfg = prod_node_config(
            tmp,
            node_id=f"prod-mesh3-{index}",
            http_port=PROD_MESH3_HTTP_PORTS[i],
            p2p_port=PROD_MESH3_P2P_PORTS[i],
            rpc_port=PROD_MESH3_RPC_PORTS[i],
            ws_port=PROD_MESH3_WS_PORTS[i],
            bootstrap_peers=bootstrap,
            mining_enabled=index == primary_miner_index,
            bridge_enabled=bridge_enabled,
            validators_manifest_path=str(manifest_path),
            wallet_source=wallet_src,
        )
        cfg_path = os.path.join(tmp, f"prod-mesh3-{index}.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        cfgs.append(cfg_path)
        urls.append(f"http://127.0.0.1:{PROD_MESH3_HTTP_PORTS[i]}")
    return cfgs[0], cfgs[1], cfgs[2], urls[0], urls[1], urls[2]

