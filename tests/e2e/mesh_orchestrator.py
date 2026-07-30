# tests/e2e/mesh_orchestrator.py — LocalMeshTopology (live process mesh)
"""Async orchestrator for real multi-node Absolute mesh processes.

Spawns ``python main.py --config …`` via ``asyncio.create_subprocess_exec``,
isolates RocksDB/SQLite data dirs per node, and supports graceful stop plus
hard kill (Unix ``SIGKILL`` / Windows ``taskkill /T /F`` — ``kill -9`` DoD).

Lab/E2E only — never imported from production ``NodeOrchestrator``.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import socket
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]

# Dedicated high ports — avoid CI smoke (:151xx) and mesh3 (:152xx).
LIVE_MESH4_HTTP_PORTS = (15480, 15481, 15482, 15483)
LIVE_MESH4_P2P_PORTS = (15400, 15401, 15402, 15403)
LIVE_MESH4_RPC_PORTS = (15445, 15446, 15447, 15448)
LIVE_MESH4_WS_PORTS = (15466, 15467, 15468, 15469)


@dataclass
class MeshNodeHandle:
    """Runtime handle for one live node process."""

    name: str
    index: int
    cfg_path: Path
    data_dir: Path
    http_port: int
    p2p_port: int
    rpc_port: int
    ws_port: int
    mining_enabled: bool
    stderr_path: Path
    process: Optional[asyncio.subprocess.Process] = None
    _stderr_fh: Any = field(default=None, repr=False)

    @property
    def http_url(self) -> str:
        return f"http://127.0.0.1:{self.http_port}"

    @property
    def rpc_url(self) -> str:
        return f"http://127.0.0.1:{self.rpc_port}"

    @property
    def pid(self) -> Optional[int]:
        if self.process is None:
            return None
        return self.process.pid

    @property
    def alive(self) -> bool:
        return self.process is not None and self.process.returncode is None


@dataclass
class MeshHttpClient:
    """Thin HTTP/JSON helpers bound to the mesh admin JWT + RPC API key."""

    admin_jwt: str = ""
    rpc_api_key: str = ""
    timeout: float = 20.0

    def get_json(self, url: str, *, timeout: Optional[float] = None) -> Dict[str, Any]:
        req = urllib.request.Request(url, method="GET")
        if self.admin_jwt:
            req.add_header("Authorization", f"Bearer {self.admin_jwt}")
        with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
            return json.loads(resp.read().decode())

    def post_json(
        self,
        base_url: str,
        path: str,
        body: Optional[Mapping[str, Any]] = None,
        *,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        data = json.dumps(dict(body or {})).encode()
        headers = {"Content-Type": "application/json"}
        if self.admin_jwt:
            headers["Authorization"] = f"Bearer {self.admin_jwt}"
        req = urllib.request.Request(
            f"{base_url.rstrip('/')}{path}",
            data=data,
            method="POST",
            headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode(errors="replace")
            if exc.code != 401:
                raise RuntimeError(f"POST {path} -> HTTP {exc.code}: {raw[:400]}") from exc
            # Retry once after assuming JWT was missing from cache.
            if not self.admin_jwt:
                raise
            headers["Authorization"] = f"Bearer {self.admin_jwt}"
            req = urllib.request.Request(
                f"{base_url.rstrip('/')}{path}",
                data=data,
                method="POST",
                headers=headers,
            )
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                return json.loads(resp.read().decode())

    def rpc_call(
        self,
        rpc_url: str,
        method: str,
        params: Optional[list] = None,
        *,
        request_id: int = 1,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": list(params or []),
        }
        data = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json"}
        if self.rpc_api_key:
            headers["X-API-Key"] = self.rpc_api_key
        req = urllib.request.Request(
            rpc_url.rstrip("/"),
            data=data,
            method="POST",
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
            return json.loads(resp.read().decode())


class LocalMeshTopology:
    """Orchestrate N live Absolute node processes with isolated storage.

    Typical lifecycle::

        async with LocalMeshTopology(node_count=4) as mesh:
            await mesh.bootstrap_leader_and_seed_followers()
            await mesh.start_all()
            await mesh.wait_all_healthy()
            await mesh.wait_peer_mesh(min_peers=2)
            …
    """

    def __init__(
        self,
        *,
        node_count: int = 4,
        root: Optional[Path] = None,
        http_ports: Sequence[int] = LIVE_MESH4_HTTP_PORTS,
        p2p_ports: Sequence[int] = LIVE_MESH4_P2P_PORTS,
        rpc_ports: Sequence[int] = LIVE_MESH4_RPC_PORTS,
        ws_ports: Sequence[int] = LIVE_MESH4_WS_PORTS,
        mesh_min_peers_before_mine: int = 0,
        deployment_mode: str = "prod",
        keep_tmpdir: bool = False,
    ) -> None:
        if node_count < 2:
            raise ValueError("node_count must be >= 2")
        if not (
            len(http_ports) >= node_count
            and len(p2p_ports) >= node_count
            and len(rpc_ports) >= node_count
            and len(ws_ports) >= node_count
        ):
            raise ValueError("port tuples shorter than node_count")

        self.node_count = int(node_count)
        # Local process mesh does not ship Redis; prod Config.validate() requires
        # redis when mesh_min_peers_before_mine >= 1. Peering is enforced by the
        # orchestrator wait_peer_mesh() DoD instead (docker prod mesh keeps Redis).
        self.mesh_min_peers_before_mine = int(mesh_min_peers_before_mine)
        self.deployment_mode = str(deployment_mode or "prod").lower()
        self.keep_tmpdir = bool(keep_tmpdir)
        self._owns_tmpdir = root is None
        self.root = Path(root) if root is not None else Path(
            tempfile.mkdtemp(prefix="abs_live_mesh4_")
        )
        self.root.mkdir(parents=True, exist_ok=True)

        self.http_ports = tuple(int(p) for p in http_ports[:node_count])
        self.p2p_ports = tuple(int(p) for p in p2p_ports[:node_count])
        self.rpc_ports = tuple(int(p) for p in rpc_ports[:node_count])
        self.ws_ports = tuple(int(p) for p in ws_ports[:node_count])

        self.nodes: Dict[str, MeshNodeHandle] = {}
        self.node_order: List[str] = []
        self.env: Dict[str, str] = {}
        self.http = MeshHttpClient()
        self.shared_wallet: Path = self.root / "_shared" / "wallet.json"
        self.manifest_path: Path = self.root / "validators.manifest.json"
        self.rpc_api_key: str = ""
        self._configs_written = False
        self._cleaned = False

    # ── lifecycle ────────────────────────────────────────────────────────────

    async def __aenter__(self) -> "LocalMeshTopology":
        self.prepare()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.cleanup()

    def prepare(self) -> None:
        """Generate env + configs (does not start processes)."""
        from runtime.prod_smoke_profile import (
            apply_prod_smoke_env,
            native_available,
            rocks_engine_available,
        )

        if self.deployment_mode in ("prod", "production") and not native_available():
            raise RuntimeError(
                "live mesh prod profile requires abs_native "
                "(ABS_REQUIRE_NATIVE_CRYPTO / P2P_NATIVE_TRANSPORT)"
            )

        busy = self.busy_ports()
        if busy:
            raise RuntimeError(f"live mesh ports busy: {busy}")

        self.env = apply_prod_smoke_env()
        self.env["PYTHONUNBUFFERED"] = "1"
        self.env.pop("MINING_ENABLED", None)
        self.env.pop("DATA_DIR", None)  # must not leak parent DATA_DIR into children
        self.rpc_api_key = str(self.env.get("RPC_API_KEYS", "")).split(",")[0].strip()
        self.http.rpc_api_key = self.rpc_api_key
        jwt = str(self.env.get("PROD_SMOKE_ADMIN_JWT") or "").strip()
        if jwt:
            self.http.admin_jwt = jwt
            os.environ["PROD_SMOKE_ADMIN_JWT"] = jwt

        self._write_shared_wallet()
        os.environ["PROD_SMOKE_WALLET_PATH"] = str(self.shared_wallet)
        self._write_validators_manifest()
        self._write_node_configs(rocks=rocks_engine_available())
        self._configs_written = True

    # ── config generation ────────────────────────────────────────────────────

    def _write_shared_wallet(self) -> str:
        from crypto.wallet import Wallet

        self.shared_wallet.parent.mkdir(parents=True, exist_ok=True)
        if not self.shared_wallet.is_file():
            w = Wallet()
            self.shared_wallet.write_text(
                json.dumps(
                    {
                        "address": w.address,
                        "public_key": w.public_key,
                        "private_key": w.private_key,
                        "label": "live-mesh4-shared-genesis",
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        with open(self.shared_wallet, encoding="utf-8") as fh:
            return str(json.load(fh).get("address") or "")

    def _write_validators_manifest(self) -> None:
        """Unique validator addresses (Config rejects duplicates).

        Genesis chain state still uses the shared wallet so all nodes share
        one founder/state_root; the manifest lists distinct identities for the
        4-node mesh (node-1 mines).
        """
        from crypto.wallet import Wallet

        miner_addr = self._write_shared_wallet()
        validators = []
        wallets_dir = self.root / "_shared" / "validator_wallets"
        wallets_dir.mkdir(parents=True, exist_ok=True)
        for i in range(1, self.node_count + 1):
            if i == 1:
                address = miner_addr
                with open(self.shared_wallet, encoding="utf-8") as fh:
                    pub = str(json.load(fh).get("public_key") or "")
            else:
                path = wallets_dir / f"validator-{i}.wallet.json"
                if not path.is_file():
                    w = Wallet()
                    path.write_text(
                        json.dumps(
                            {
                                "address": w.address,
                                "public_key": w.public_key,
                                "private_key": w.private_key,
                                "label": f"live-mesh4-validator-{i}",
                            },
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                with open(path, encoding="utf-8") as fh:
                    row = json.load(fh)
                address = str(row.get("address") or "")
                pub = str(row.get("public_key") or "")
            validators.append(
                {
                    "index": i,
                    "node_id": f"live-mesh4-{i}",
                    "address": address,
                    "public_key": pub,
                    "mines": i == 1,
                    "stake": 5000,
                    "shard_id": 0,
                }
            )
        payload = {
            "version": 1,
            "description": "Live mesh4 E2E validator set (unique addresses, shared genesis)",
            "validators": validators,
        }
        self.manifest_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _storage_fields(self, data_dir: Path, *, rocks: bool) -> Dict[str, Any]:
        if rocks:
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

    def _node_config(self, index: int, *, rocks: bool) -> Dict[str, Any]:
        from runtime.mainnet_constants import MAINNET_V1_CHAIN_ID
        from runtime.prod_smoke_profile import prod_node_config

        name = f"node-{index}"
        data_dir = self.root / name
        data_dir.mkdir(parents=True, exist_ok=True)

        # Full-mesh dial list (not only lower-index peers) so the miner also
        # reconnects outbound and SyncEngine sees peer tips for catch-up.
        bootstrap = [
            f"127.0.0.1:{self.p2p_ports[j]}"
            for j in range(self.node_count)
            if j != (index - 1)
        ]
        mining = index == 1
        # prod_node_config stores under ``{root}/{node_id}/`` — keep id == folder name.
        cfg = prod_node_config(
            str(self.root),
            node_id=name,
            http_port=self.http_ports[index - 1],
            p2p_port=self.p2p_ports[index - 1],
            rpc_port=self.rpc_ports[index - 1],
            ws_port=self.ws_ports[index - 1],
            bootstrap_peers=bootstrap,
            mining_enabled=mining,
            bridge_enabled=False,
            validators_manifest_path=str(self.manifest_path),
            wallet_source=self.shared_wallet,
        )
        cfg["node_id"] = f"live-mesh4-{index}"
        cfg.update(self._storage_fields(data_dir, rocks=rocks))
        cfg["log_file"] = str(data_dir / "node.log")
        cfg["mesh_min_peers_before_mine"] = (
            self.mesh_min_peers_before_mine if mining else 0
        )
        cfg["follower_genesis_sync"] = not mining
        # Slower blocks → followers can finish catch_up between tips.
        cfg["block_time"] = 25
        cfg["chain_id"] = MAINNET_V1_CHAIN_ID
        cfg["deployment_mode"] = self.deployment_mode
        cfg["network_name"] = "Absolute Live Mesh4 E2E"
        db_path = Path(str(cfg["db_path"])).resolve()
        root_res = self.root.resolve()
        if root_res not in db_path.parents and db_path.parent != root_res:
            raise RuntimeError(f"{name} db_path escapes mesh root: {db_path}")
        return cfg

    def _write_node_configs(self, *, rocks: bool) -> None:
        self.nodes.clear()
        self.node_order.clear()
        for index in range(1, self.node_count + 1):
            name = f"node-{index}"
            cfg = self._node_config(index, rocks=rocks)
            cfg_path = self.root / f"{name}.json"
            cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
            data_dir = self.root / name
            handle = MeshNodeHandle(
                name=name,
                index=index,
                cfg_path=cfg_path,
                data_dir=data_dir,
                http_port=self.http_ports[index - 1],
                p2p_port=self.p2p_ports[index - 1],
                rpc_port=self.rpc_ports[index - 1],
                ws_port=self.ws_ports[index - 1],
                mining_enabled=bool(cfg.get("mining_enabled")),
                stderr_path=self.root / f"{name}.stderr.log",
            )
            self.nodes[name] = handle
            self.node_order.append(name)

    # ── port / health probes ─────────────────────────────────────────────────

    def busy_ports(self) -> List[int]:
        busy: List[int] = []
        for port in (*self.http_ports, *self.p2p_ports, *self.rpc_ports, *self.ws_ports):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.35)
            try:
                if sock.connect_ex(("127.0.0.1", int(port))) == 0:
                    busy.append(int(port))
            finally:
                sock.close()
        return busy

    def node(self, name: str) -> MeshNodeHandle:
        if name not in self.nodes:
            raise KeyError(f"unknown node {name!r}; known={list(self.nodes)}")
        return self.nodes[name]

    def status(self, name: str) -> Dict[str, Any]:
        return self.http.get_json(f"{self.node(name).http_url}/status", timeout=12)

    def peers(self, name: str) -> Dict[str, Any]:
        return self.http.get_json(f"{self.node(name).http_url}/peers", timeout=12)

    def finality_stats(self, name: str) -> Dict[str, Any]:
        return self.http.get_json(
            f"{self.node(name).http_url}/finality/stats", timeout=15
        )

    # ── process control ──────────────────────────────────────────────────────

    async def start_node(self, name: str, *, append_log: bool = False) -> MeshNodeHandle:
        handle = self.node(name)
        if handle.alive:
            return handle

        mode = "a" if append_log and handle.stderr_path.is_file() else "w"
        handle._stderr_fh = open(handle.stderr_path, mode, encoding="utf-8")
        creationflags = 0
        if sys.platform == "win32":
            creationflags = getattr(subprocess_mod(), "CREATE_NEW_PROCESS_GROUP", 0)

        # Capture stdout+stderr — Config/boot fatals often print to stdout.
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "main.py",
            "--config",
            str(handle.cfg_path),
            cwd=str(ROOT),
            env=dict(self.env),
            stdout=handle._stderr_fh,
            stderr=asyncio.subprocess.STDOUT,
            creationflags=creationflags,
        )
        handle.process = proc
        return handle

    async def start_all(self, *, stagger_sec: float = 1.5) -> None:
        for name in self.node_order:
            await self.start_node(name)
            if stagger_sec > 0:
                await asyncio.sleep(stagger_sec)

    def _set_mining_enabled(self, name: str, enabled: bool) -> None:
        cfg_path = self.node(name).cfg_path
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
        raw["mining_enabled"] = bool(enabled)
        cfg_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        self.node(name).mining_enabled = bool(enabled)

    async def start_mesh_hold_mining_until_synced(
        self,
        *,
        stagger_sec: float = 1.5,
        sync_timeout_sec: float = 240.0,
    ) -> Dict[str, Any]:
        """Start followers first, leader with mining OFF, sync equal tip, then arm mining.

        Prevents the industrial [tip+1, tip, tip, tip] trap: with
        ``mesh_min_peers_before_mine=0`` the leader otherwise forges the next
        block before followers finish P2P catch-up, ConsistencyService stays
        BehindOpen, and further mining + import freeze.
        """
        leader = self.node_order[0]
        followers = self.node_order[1:]

        # Leader must not forge while the mesh is forming after clone.
        self._set_mining_enabled(leader, False)

        for name in followers:
            await self.start_node(name)
            if stagger_sec > 0:
                await asyncio.sleep(stagger_sec)
        await self.start_node(leader)
        await self.wait_all_healthy(timeout_sec=240)
        await self.ensure_admin_jwt(leader)

        # Tip-repair every node so tip-probe binds a healthy live root.
        for name in self.node_order:
            try:
                await self.trigger_tip_repair(name)
            except Exception:
                pass

        await self.wait_peer_mesh(min_peers=2, timeout_sec=240)
        synced = await self.catch_up_cluster(
            self.node_order, timeout_sec=sync_timeout_sec
        )

        # Arm mining only after equal head — then live replication can be proven.
        await self.stop_node(leader, graceful_timeout=25)
        await asyncio.sleep(1.0)
        self._set_mining_enabled(leader, True)
        await self.start_node(leader, append_log=True)
        await self.wait_healthy(leader, timeout_sec=180)
        await self.ensure_admin_jwt(leader)
        await self.reconnect_mesh(self.node_order)
        return synced

    async def heal_laggers_by_reclone(
        self, laggers: Sequence[str], *, leader: str = "node-1"
    ) -> None:
        """Quiesce leader, reclone chainstore into laggers, restart (mesh3 auto-heal)."""
        from storage.chain_clone import clone_chain_data

        alive_followers = [
            n for n in self.node_order if n != leader and n not in laggers and self.node(n).alive
        ]
        # Stop everyone that touches Rocks before clone.
        for name in list(laggers) + [leader]:
            if self.node(name).alive:
                await self.stop_node(name, graceful_timeout=25)
        await asyncio.sleep(1.5)

        leader_dir = self.node(leader).data_dir
        for name in laggers:
            dest = self.node(name).data_dir
            dest.mkdir(parents=True, exist_ok=True)
            wallet = dest / "wallet.json"
            wallet_bytes = wallet.read_bytes() if wallet.is_file() else None
            clone_chain_data(str(leader_dir), str(dest))
            if wallet_bytes is not None:
                wallet.write_bytes(wallet_bytes)

        # Restart leader with current mining flag, then laggers.
        await self.start_node(leader, append_log=True)
        await self.wait_healthy(leader, timeout_sec=180)
        for name in laggers:
            await self.start_node(name, append_log=True)
            await self.wait_healthy(name, timeout_sec=180)
        await self.reconnect_mesh([leader, *laggers, *alive_followers])

    async def stop_node(self, name: str, *, graceful_timeout: float = 20.0) -> None:
        handle = self.node(name)
        proc = handle.process
        if proc is None or proc.returncode is not None:
            handle.process = None
            self._close_stderr(handle)
            return
        try:
            proc.terminate()
        except ProcessLookupError:
            handle.process = None
            self._close_stderr(handle)
            return
        try:
            await asyncio.wait_for(proc.wait(), timeout=graceful_timeout)
        except asyncio.TimeoutError:
            await self.kill_hard(name)
            return
        handle.process = None
        self._close_stderr(handle)

    async def kill_hard(self, name: str) -> None:
        """Physical crash: Unix SIGKILL / Windows taskkill /T /F (kill -9 DoD)."""
        handle = self.node(name)
        proc = handle.process
        if proc is None:
            return
        pid = proc.pid
        if pid is None:
            return

        if sys.platform == "win32":
            try:
                killer = await asyncio.create_subprocess_exec(
                    "taskkill",
                    "/PID",
                    str(pid),
                    "/T",
                    "/F",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.wait_for(killer.wait(), timeout=30.0)
            except Exception:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
        else:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except Exception:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass

        try:
            await asyncio.wait_for(proc.wait(), timeout=30.0)
        except (asyncio.TimeoutError, ProcessLookupError):
            pass
        handle.process = None
        self._close_stderr(handle)

    async def restart_node(self, name: str, *, hard: bool = False) -> MeshNodeHandle:
        if hard:
            await self.kill_hard(name)
        else:
            await self.stop_node(name)
        await asyncio.sleep(1.0)
        return await self.start_node(name, append_log=True)

    def _close_stderr(self, handle: MeshNodeHandle) -> None:
        fh = handle._stderr_fh
        handle._stderr_fh = None
        if fh is not None:
            try:
                fh.flush()
                fh.close()
            except Exception:
                pass

    async def stop_all(self, *, graceful_timeout: float = 15.0) -> None:
        # Reverse order: followers first, miner last.
        for name in reversed(self.node_order):
            await self.stop_node(name, graceful_timeout=graceful_timeout)

    async def cleanup(self) -> None:
        if self._cleaned:
            return
        self._cleaned = True
        try:
            await self.stop_all()
        finally:
            for handle in self.nodes.values():
                self._close_stderr(handle)
            if self._owns_tmpdir and not self.keep_tmpdir:
                import shutil

                try:
                    shutil.rmtree(self.root, ignore_errors=True)
                except Exception:
                    pass

    # ── readiness / mesh waits ───────────────────────────────────────────────

    async def wait_healthy(self, name: str, *, timeout_sec: float = 180.0) -> None:
        handle = self.node(name)
        deadline = time.monotonic() + float(timeout_sec)
        last_err = ""
        while time.monotonic() < deadline:
            if handle.process is not None and handle.process.returncode is not None:
                tail = self._stderr_tail(handle, 40)
                raise RuntimeError(
                    f"{name} exited early rc={handle.process.returncode}\n{tail}"
                )
            try:
                self.http.get_json(f"{handle.http_url}/health/live", timeout=4)
                return
            except Exception as exc:
                last_err = str(exc)
            await asyncio.sleep(2.0)
        raise TimeoutError(
            f"{name} health timeout ({timeout_sec}s): {last_err}\n"
            f"{self._stderr_tail(handle, 60)}"
        )

    async def wait_all_healthy(self, *, timeout_sec: float = 180.0) -> None:
        await asyncio.gather(
            *(self.wait_healthy(n, timeout_sec=timeout_sec) for n in self.node_order)
        )

    async def wait_peer_count(
        self, name: str, min_peers: int, *, timeout_sec: float = 120.0
    ) -> int:
        deadline = time.monotonic() + float(timeout_sec)
        last = 0
        while time.monotonic() < deadline:
            try:
                last = int(self.peers(name).get("count", 0) or 0)
                if last >= int(min_peers):
                    return last
            except Exception:
                pass
            # Nudge reconnect on live mesh.
            try:
                self.http.post_json(
                    self.node(name).http_url,
                    "/p2p/reconnect",
                    {"timeout": 15},
                    timeout=25,
                )
            except Exception:
                pass
            await asyncio.sleep(2.0)
        raise TimeoutError(f"{name} peers={last} < {min_peers}")

    async def wait_peer_mesh(
        self, *, min_peers: int = 2, timeout_sec: float = 180.0
    ) -> None:
        deadline = time.monotonic() + float(timeout_sec)
        while time.monotonic() < deadline:
            ok = True
            for name in self.node_order:
                if not self.node(name).alive:
                    continue
                try:
                    count = int(self.peers(name).get("count", 0) or 0)
                except Exception:
                    count = 0
                if count < min_peers:
                    ok = False
                    try:
                        self.http.post_json(
                            self.node(name).http_url,
                            "/p2p/reconnect",
                            {"timeout": 15},
                            timeout=25,
                        )
                    except Exception:
                        pass
            if ok:
                return
            await asyncio.sleep(3.0)
        raise TimeoutError(f"peer mesh did not reach min_peers={min_peers}")

    async def wait_height_at_least(
        self, name: str, height: int, *, timeout_sec: float = 180.0
    ) -> int:
        deadline = time.monotonic() + float(timeout_sec)
        last = 0
        while time.monotonic() < deadline:
            try:
                last = int(self.status(name).get("height", 0) or 0)
                if last >= int(height):
                    return last
            except Exception:
                pass
            await asyncio.sleep(2.0)
        raise TimeoutError(f"{name} height={last} < {height}")

    async def pause_mining_sync_resume(
        self,
        names: Optional[Sequence[str]] = None,
        *,
        timeout_sec: float = 300.0,
    ) -> Dict[str, Any]:
        """Stop leader forging, sync cluster to equal head, optionally re-arm mining."""
        target = list(names) if names is not None else list(self.node_order)
        leader = self.node_order[0]
        resume_mining = bool(self.node(leader).mining_enabled)

        if self.node(leader).alive:
            await self.stop_node(leader, graceful_timeout=25)
            await asyncio.sleep(1.0)
        self._set_mining_enabled(leader, False)
        await self.start_node(leader, append_log=True)
        await self.wait_healthy(leader, timeout_sec=180)
        await self.ensure_admin_jwt(leader)

        for name in target:
            if not self.node(name).alive:
                continue
            try:
                await self.trigger_tip_repair(name)
            except Exception:
                pass

        await self.reconnect_mesh(target)
        synced = await self.wait_common_head(
            target,
            timeout_sec=timeout_sec,
            max_spread=0,
            require_equal_height=True,
            auto_pause_mining=False,
        )

        if resume_mining:
            await self.stop_node(leader, graceful_timeout=25)
            await asyncio.sleep(1.0)
            self._set_mining_enabled(leader, True)
            await self.start_node(leader, append_log=True)
            await self.wait_healthy(leader, timeout_sec=180)
            await self.ensure_admin_jwt(leader)
            await self.reconnect_mesh(target)
        return synced

    async def wait_common_head(
        self,
        names: Optional[Sequence[str]] = None,
        *,
        timeout_sec: float = 240.0,
        max_spread: int = 1,
        require_equal_height: bool = False,
        auto_pause_mining: bool = True,
    ) -> Dict[str, Any]:
        target = list(names) if names is not None else [
            n for n in self.node_order if self.node(n).alive
        ]
        deadline = time.monotonic() + float(timeout_sec)
        last: Dict[str, Any] = {}
        round_i = 0
        paused_once = False
        while time.monotonic() < deadline:
            round_i += 1
            try:
                statuses = {n: self.status(n) for n in target}
                heights = [int(s.get("height", 0) or 0) for s in statuses.values()]
                heads = [(s.get("head_hash") or "").lower() for s in statuses.values()]
                last = {
                    "heights": heights,
                    "heads": heads,
                    "statuses": statuses,
                }
                spread_ok = bool(heights) and (max(heights) - min(heights) <= max_spread)
                equal_h = bool(heights) and max(heights) == min(heights)
                height_ok = equal_h if require_equal_height else spread_ok
                if (
                    heights
                    and min(heights) >= 1
                    and height_ok
                    and heads[0]
                    and len(set(heads)) == 1
                ):
                    return last
            except Exception:
                pass

            # If the leader already raced ahead, pause mining once so followers
            # can finish Path-A catch-up without ConsistencyService locking tip.
            if (
                auto_pause_mining
                and require_equal_height
                and not paused_once
                and round_i >= 3
                and last.get("heights")
                and max(last["heights"]) - min(last["heights"]) >= 1
            ):
                paused_once = True
                remaining = max(60.0, deadline - time.monotonic())
                return await self.pause_mining_sync_resume(
                    target, timeout_sec=remaining
                )

            if round_i % 2 == 1:
                await self.reconnect_mesh(target)
            await self.catch_up_laggers(target, sync_timeout_sec=45.0)
            await asyncio.sleep(2.0)

        # Enrich timeout with sync refuse counters when present.
        detail = dict(last)
        try:
            for n in target:
                st = self.status(n)
                detail.setdefault("diagnostics", {})[n] = {
                    "height": st.get("height"),
                    "head": (st.get("head_hash") or "")[:16],
                    "peers": (self.peers(n) or {}).get("count"),
                    "p2p_sync_status": st.get("p2p_sync_status"),
                    "state_root": (st.get("state_root") or "")[:16],
                }
        except Exception:
            pass
        raise TimeoutError(f"common head not reached: {detail}")

    async def reconnect_mesh(self, names: Optional[Sequence[str]] = None) -> None:
        """Nudge peer dials. ``/p2p/reconnect`` is prod-blocked — fall back to reconcile."""
        target = list(names) if names is not None else [
            n for n in self.node_order if self.node(n).alive
        ]

        async def _one(name: str) -> None:
            # Dev/staging: reconnect is available. Prod: 403 → use reconcile.
            try:
                await asyncio.to_thread(
                    self.http.post_json,
                    self.node(name).http_url,
                    "/p2p/reconnect",
                    {"timeout": 20},
                    timeout=30,
                )
                return
            except Exception:
                pass
            try:
                await self.trigger_reconcile(name, timeout_sec=30.0)
            except Exception:
                pass

        await asyncio.gather(*(_one(n) for n in target))

    async def catch_up_laggers(
        self,
        names: Optional[Sequence[str]] = None,
        *,
        sync_timeout_sec: float = 45.0,
    ) -> None:
        """Parallel fast-sync + reconcile for nodes behind the tip.

        Honesty: ``/chain/consistency/repair`` is prod-blocked (403). Recovery
        uses live ``/sync/fast-sync`` + ``/sync/reconcile`` only.
        """
        target = list(names) if names is not None else [
            n for n in self.node_order if self.node(n).alive
        ]
        try:
            heights = {
                n: int(self.status(n).get("height", 0) or 0)
                for n in target
                if self.node(n).alive
            }
        except Exception:
            return
        if not heights:
            return
        tip = max(heights.values())
        laggers = [n for n, h in heights.items() if h < tip]
        if not laggers:
            return

        async def _sync_one(name: str) -> None:
            # Best-effort tip repair when not prod-blocked.
            repair = await self.trigger_tip_repair(name)
            if repair.get("skipped"):
                pass
            try:
                await self.trigger_fast_sync(name, timeout_sec=sync_timeout_sec)
            except Exception:
                pass
            try:
                await self.trigger_reconcile(
                    name, timeout_sec=min(45.0, sync_timeout_sec)
                )
            except Exception:
                pass

        await asyncio.gather(*(_sync_one(n) for n in laggers))

    async def catch_up_cluster(
        self,
        names: Optional[Sequence[str]] = None,
        *,
        timeout_sec: float = 300.0,
    ) -> Dict[str, Any]:
        """Industrial bootstrap catch-up: reconnect → sync until equal tip+head."""
        target = list(names) if names is not None else list(self.node_order)
        await self.reconnect_mesh(target)
        await asyncio.sleep(2.0)
        return await self.wait_common_head(
            target,
            timeout_sec=timeout_sec,
            max_spread=0,
            require_equal_height=True,
            auto_pause_mining=False,
        )

    # ── sync / repair (live HTTP) ────────────────────────────────────────────

    async def trigger_fast_sync(
        self, name: str, *, timeout_sec: float = 45.0
    ) -> Dict[str, Any]:
        # API clamps timeout to >=30s; keep HTTP budget slightly above body.
        body_timeout = max(30.0, float(timeout_sec))
        return await asyncio.to_thread(
            self.http.post_json,
            self.node(name).http_url,
            "/sync/fast-sync",
            {"timeout": int(body_timeout)},
            timeout=body_timeout + 20,
        )

    async def trigger_reconcile(
        self, name: str, *, timeout_sec: float = 45.0
    ) -> Dict[str, Any]:
        body_timeout = max(30.0, float(timeout_sec))
        return await asyncio.to_thread(
            self.http.post_json,
            self.node(name).http_url,
            "/sync/reconcile",
            {"timeout": int(body_timeout)},
            timeout=body_timeout + 20,
        )

    async def trigger_tip_repair(self, name: str) -> Dict[str, Any]:
        """POST /chain/consistency/repair — soft-skip when prod-blocked (403)."""
        try:
            return await asyncio.to_thread(
                self.http.post_json,
                self.node(name).http_url,
                "/chain/consistency/repair",
                {},
                timeout=60,
            )
        except RuntimeError as exc:
            msg = str(exc)
            if "HTTP 403" in msg or "disabled in production" in msg:
                return {
                    "success": False,
                    "skipped": True,
                    "reason": "prod_blocked",
                    "detail": msg[:200],
                }
            raise
        except urllib.error.HTTPError as exc:
            if exc.code == 403:
                return {
                    "success": False,
                    "skipped": True,
                    "reason": "prod_blocked",
                }
            raise

    async def ensure_admin_jwt(self, name: str = "node-1") -> str:
        if self.http.admin_jwt:
            return self.http.admin_jwt
        url = self.node(name).http_url
        try:
            token_resp = await asyncio.to_thread(
                self.http.get_json, f"{url}/auth/token?address=live-mesh-admin", timeout=10
            )
            token = str(token_resp.get("token") or "")
        except Exception:
            token = ""
        if not token:
            token = str(self.env.get("PROD_SMOKE_ADMIN_JWT") or "")
        if not token:
            raise RuntimeError("admin JWT unavailable for live mesh")
        self.http.admin_jwt = token
        os.environ["PROD_SMOKE_ADMIN_JWT"] = token
        return token

    # ── bootstrap / seed (RocksDB isolation) ──────────────────────────────────

    async def bootstrap_leader_and_seed_followers(self) -> None:
        """Start miner alone, mine ≥1 block, quiesce, clone chainstore to followers.

        Matches industrial prod-mesh3 honesty: never share a live RocksDB lock
        across processes; each follower gets an isolated clone then rejoins live.
        """
        if not self._configs_written:
            self.prepare()

        leader = self.node_order[0]
        leader_cfg_path = self.node(leader).cfg_path
        raw = json.loads(leader_cfg_path.read_text(encoding="utf-8"))
        # Solo bootstrap must mine without peers; restore mesh gate after seed.
        raw["mesh_min_peers_before_mine"] = 0
        leader_cfg_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")

        await self.start_node(leader)
        await self.wait_healthy(leader, timeout_sec=180)
        await self.ensure_admin_jwt(leader)

        try:
            await self.wait_height_at_least(leader, 1, timeout_sec=120)
        except TimeoutError:
            pass

        await self.stop_node(leader, graceful_timeout=25)
        await asyncio.sleep(1.5)

        # Restore production mesh mining gate for the live 4-node run.
        raw["mesh_min_peers_before_mine"] = self.mesh_min_peers_before_mine
        leader_cfg_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")

        from storage.chain_clone import clone_chain_data

        leader_dir = self.node(leader).data_dir
        has_chain = (
            (leader_dir / "chainstore").is_dir()
            or (leader_dir / "chain.db").is_file()
            or (leader_dir / "blockchain.db").is_file()
        )
        if has_chain:
            for name in self.node_order[1:]:
                dest = self.node(name).data_dir
                dest.mkdir(parents=True, exist_ok=True)
                wallet = dest / "wallet.json"
                wallet_bytes = wallet.read_bytes() if wallet.is_file() else None
                clone_chain_data(str(leader_dir), str(dest))
                if wallet_bytes is not None:
                    wallet.write_bytes(wallet_bytes)

    # ── RPC / tx helpers ─────────────────────────────────────────────────────

    async def rpc(self, name: str, method: str, params: Optional[list] = None) -> Any:
        handle = self.node(name)
        resp = await asyncio.to_thread(
            self.http.rpc_call, handle.rpc_url, method, params
        )
        if "error" in resp and resp["error"]:
            raise RuntimeError(f"RPC {method} error: {resp['error']}")
        return resp.get("result")

    async def send_signed_tx(self, name: str = "node-1") -> Dict[str, Any]:
        """Signed /tx/send on a live prod-profile node (no auto_sign mocks)."""
        from crypto.wallet import Wallet
        from runtime.mainnet_constants import MAINNET_V1_CHAIN_ID

        await self.ensure_admin_jwt(name)
        handle = self.node(name)
        st = self.status(name)
        wallet = Wallet.import_wallet(str(self.shared_wallet))
        chain_id = int(st.get("chain_id") or MAINNET_V1_CHAIN_ID)
        addr_info = self.http.get_json(f"{handle.http_url}/address/{wallet.address}")
        nonce = int(addr_info.get("nonce", 0) or 0)
        balance = float(addr_info.get("balance", 0) or 0)
        if balance < 0.5:
            raise RuntimeError(
                f"signer balance too low ({balance}); wait for miner rewards"
            )
        seed = f"live-mesh-tx-{time.time_ns()}-{os.getpid()}"
        from crypto import native

        recipient = "0x" + native.sha256_hex(seed.encode())[:40]
        signed = wallet.sign_transaction(
            recipient,
            1,
            nonce,
            chain_id=chain_id,
            gas_limit=21000,
        )
        body = {**signed, "gas": 21000}
        return await asyncio.to_thread(
            self.http.post_json, handle.http_url, "/tx/send", body, timeout=30
        )

    def _stderr_tail(self, handle: MeshNodeHandle, lines: int = 40) -> str:
        try:
            if not handle.stderr_path.is_file():
                return "(no stderr log)"
            text = handle.stderr_path.read_text(encoding="utf-8", errors="replace")
            parts = text.splitlines()
            return "\n".join(parts[-lines:])
        except Exception as exc:
            return f"(stderr read failed: {exc})"


def subprocess_mod():
    import subprocess

    return subprocess


def require_live_mesh_prereqs() -> None:
    """Raise Skip-worthy errors for pytest when native/ports unavailable."""
    from runtime.prod_smoke_profile import native_available

    if not native_available():
        raise RuntimeError("abs_native not available")
    busy = []
    for port in (
        *LIVE_MESH4_HTTP_PORTS,
        *LIVE_MESH4_P2P_PORTS,
        *LIVE_MESH4_RPC_PORTS,
        *LIVE_MESH4_WS_PORTS,
    ):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.25)
        try:
            if sock.connect_ex(("127.0.0.1", int(port))) == 0:
                busy.append(int(port))
        finally:
            sock.close()
    if busy:
        raise RuntimeError(f"ports busy: {busy}")
