#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Absolute Blockchain — единая конфигурация узла.
Все параметры системы берутся отсюда.
"""

import json
import os
from dataclasses import dataclass, field
from typing import List, Optional

from runtime.env_loader import env_str, env_int, env_bool, env_list


@dataclass
class Config:
    # ── Идентификация сети ──────────────────────────────────────────────────
    chain_id: int = 77777                 # Absolute Devnet (see node.example.json)
    network_name: str = "Absolute"
    node_version: str = "1.2.0-industrial"
    node_id: str = "node-1"
    deployment_mode: str = "dev"          # dev | staging | prod

    # ── Монета (токеномика D.U.P. / Uladzimir Dabranski) ───────────────────
    coin_symbol: str = "ABS"
    coin_name: str = "Absolute"
    max_supply: int = 221_000_000       # жёсткий лимит: 221 млн ABS
    genesis_supply: int = 110_500_000   # genesis-эмиссия (без mining pool)
    founder_percent: float = 17.4       # доля основателя D.U.P.
    founder_amount: float = 38_454_000  # 17.4% от 221M
    founder_address: str = ""           # заполняется из wallet при запуске
    founder_initials: str = "D.U.P."
    founder_name: str = "Uladzimir Dabranski"
    block_reward: float = 50.0          # вознаграждение майнера за блок (из mining pool)
    burn_rate: float = 0.02             # 2% каждой комиссии сжигается навсегда
    burn_address: str = "0x000000000000000000000000000000000000dead"
    base_gas_price: int = 21_000        # базовая стоимость перевода в gas units
    gas_price_wei: float = 0.000_000_1  # цена одного gas в ABS

    # ── Сервера ─────────────────────────────────────────────────────────────
    rpc_host: str = "0.0.0.0"
    rpc_port: int = 8545        # JSON-RPC (Ethereum-совместимый)
    http_host: str = "0.0.0.0"
    http_port: int = 8080       # REST API
    ws_host: str = "0.0.0.0"
    ws_port: int = 8766         # WebSocket
    p2p_host: str = "0.0.0.0"
    p2p_port: int = 5000        # P2P сеть

    # ── База данных ─────────────────────────────────────────────────────────
    db_path: str = "data/blockchain.db"
    db_wal_mode: bool = True            # WAL для производительности SQLite

    # ── Майнинг / Консенсус ─────────────────────────────────────────────────
    block_time: int = 15                # секунд между блоками
    epoch_size: int = 32                # блоков в эпохе (staking release)
    max_tx_per_block: int = 500
    mining_enabled: bool = True
    miner_address: str = ""             # заполняется из wallet при запуске
    signing_address: str = ""           # operational wallet for API signing
    validator_count: int = 21
    min_stake: float = 1000.0           # минимальный стейк валидатора
    require_signatures: bool = False    # prod / node.json: true — reject unsigned txs
    enforce_proposer: bool = True       # reject blocks from unknown/slashed proposers
    verify_peer_state_root: bool = True # compare state_root on P2P import
    state_root_strict_p2p: bool = True  # strict state_root on P2P import above baseline
    state_root_legacy_cutoff_height: int = 0  # blocks <= cutoff: warn on drift; above: strict
    monitor_port: int = 0               # 0 = http_port + 12 (8092 for :8080)
    rpc_proxy_port: int = 0             # 0 = http_port + 2 (8082 for :8080)
    monitor_enabled: bool = True

    # ── P2P ─────────────────────────────────────────────────────────────────
    bootstrap_peers: List[str] = field(default_factory=list)
    max_peers: int = 50
    testnet_expected_peers: int = 1     # mesh health threshold (3-node devnet: 2 on hub)
    testnet_expected_validators: int = 0  # Wave 55: 5-validator devnet
    testnet_validator_index: int = 0      # this node's slot in manifest (1..5)
    testnet_validators_manifest: str = "" # docker/validators.devnet5.json
    peer_timeout: int = 30              # секунд до отключения неактивного пира
    sync_batch_size: int = 100          # блоков за один запрос синхронизации

    # ── EVM ─────────────────────────────────────────────────────────────────
    evm_enabled: bool = True
    evm_gas_limit: int = 8_000_000
    feature_nft: bool = True
    feature_zk: bool = True
    feature_sharding: bool = True
    feature_oracles: bool = True
    feature_wasm: bool = True
    feature_plasma: bool = True
    feature_lightning: bool = True
    feature_pq: bool = True
    feature_mev: bool = True
    feature_ai_agents: bool = True

    # ── Мост (Cross-chain bridge) ────────────────────────────────────────────
    bridge_enabled: bool = True
    bridge_mode: str = "rust"           # "rust" | explicit dev/test-only "simulator"
    bridge_auto_confirm_sec: int = 0    # 0 = manual POST /bridge/confirm-lock only
    bridge_require_l1_proof: bool = False
    bridge_dev_adapter_enabled: bool = False  # explicit dev/test CrossChainBridge adapter
    rust_bridge_path: str = "bridge/abs_bridge_bin"
    bridge_oracle_secret: str = ""      # HMAC secret for /bridge/oracle/* relayer
    bridge_l1_queue_path: str = "data/bridge_l1_queue.json"

    # ── Логирование ─────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_file: str = "data/node.log"
    log_json: bool = False                # structured JSON logs (prod)

    # ── Промышленный профиль ────────────────────────────────────────────────
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    jwt_enforce_admin: bool = False       # prod: требовать JWT на POST/admin
    require_wallet_file: bool = False     # prod: не генерировать кошелёк автоматически
    enable_cors_rpc_proxy: bool = True    # dev-only RPC proxy :8082
    allow_insecure_public_bind: bool = False
    sqlite_synchronous: str = "NORMAL"      # prod: FULL
    metrics_enabled: bool = True
    require_native_crypto: bool = False     # prod: require abs_native PyO3 kernels

    # ── Scale / HA (Phase 5) ────────────────────────────────────────────────
    redis_url: str = ""                     # redis://localhost:6379/0
    redis_rate_limit_enabled: bool = False  # distributed rate limit
    rate_limit_rpm: int = 120               # requests per minute per IP

    # ── RPC Security (Phase 2b) ─────────────────────────────────────────────
    rpc_api_key_required: bool = False      # prod: требовать ключ на :8545
    rpc_api_keys: List[str] = field(default_factory=list)  # из RPC_API_KEYS env

    # ────────────────────────────────────────────────────────────────────────

    @classmethod
    def from_json(cls, path: str) -> "Config":
        """Загрузить конфигурацию из JSON-файла."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cfg = cls()
        for k, v in data.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        return cfg

    def to_json(self, path: str) -> None:
        """Сохранить конфигурацию в JSON-файл."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        data = {k: v for k, v in self.__dict__.items() if not k.startswith("_")}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def base_fee(self) -> float:
        """Базовая комиссия за обычный перевод в ABS."""
        return self.base_gas_price * self.gas_price_wei

    def resolved_monitor_port(self) -> int:
        return self.monitor_port or (self.http_port + 12)

    def resolved_rpc_proxy_port(self) -> int:
        return self.rpc_proxy_port or (self.http_port + 2)

    @property
    def is_production(self) -> bool:
        return self.deployment_mode == "prod"

    def resolve_rust_bridge_path(self) -> str:
        """Resolve rust bridge binary (incl. .exe on Windows and project-relative paths)."""
        candidates = [self.rust_bridge_path, self.rust_bridge_path + ".exe"]
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for base in candidates:
            if os.path.isfile(base):
                return base
            rel = os.path.join(root, base)
            if os.path.isfile(rel):
                return rel
        return self.rust_bridge_path

    def apply_env(self) -> "Config":
        """Переопределяет поля из переменных окружения (.env / Docker / K8s)."""
        data_dir = env_str("DATA_DIR")
        if data_dir:
            self.db_path = os.path.join(data_dir, "blockchain.db")
            self.log_file = os.path.join(data_dir, "node.log")

        self.node_id = env_str("NODE_ID", self.node_id)
        self.deployment_mode = env_str("DEPLOYMENT_MODE", self.deployment_mode).lower()
        self.chain_id = env_int("CHAIN_ID", self.chain_id)
        self.rpc_host = env_str("RPC_HOST", self.rpc_host)
        self.http_host = env_str("HTTP_HOST", self.http_host)
        self.ws_host = env_str("WS_HOST", self.ws_host)
        self.p2p_host = env_str("P2P_HOST", self.p2p_host)
        self.rpc_port = env_int("RPC_PORT", self.rpc_port)
        self.http_port = env_int("HTTP_PORT", env_int("WEB_PORT", self.http_port))
        self.ws_port = env_int("WS_PORT", self.ws_port)
        self.p2p_port = env_int("P2P_PORT", self.p2p_port)
        self.log_level = env_str("LOG_LEVEL", self.log_level)
        self.log_json = env_bool("LOG_JSON", self.log_json)
        self.mining_enabled = env_bool("MINING_ENABLED", self.mining_enabled)
        self.require_signatures = env_bool(
            "REQUIRE_SIGNATURES",
            self.require_signatures if not self.is_production else True,
        )
        self.enforce_proposer = env_bool("ENFORCE_PROPOSER", self.enforce_proposer)
        self.verify_peer_state_root = env_bool(
            "VERIFY_PEER_STATE_ROOT", self.verify_peer_state_root
        )
        self.state_root_strict_p2p = env_bool(
            "STATE_ROOT_STRICT_P2P", self.state_root_strict_p2p
        )
        self.state_root_legacy_cutoff_height = env_int(
            "STATE_ROOT_LEGACY_CUTOFF_HEIGHT",
            self.state_root_legacy_cutoff_height,
        )
        self.monitor_enabled = env_bool("MONITOR_ENABLED", self.monitor_enabled)
        self.monitor_port = env_int("MONITOR_PORT", self.monitor_port)
        self.rpc_proxy_port = env_int("RPC_PROXY_PORT", self.rpc_proxy_port)
        self.metrics_enabled = env_bool("METRICS_ENABLED", self.metrics_enabled)
        self.require_native_crypto = env_bool(
            "ABS_REQUIRE_NATIVE_CRYPTO",
            self.require_native_crypto if not self.is_production else True,
        )
        self.jwt_enforce_admin = env_bool("JWT_ENFORCE_ADMIN", self.jwt_enforce_admin)
        self.enable_cors_rpc_proxy = env_bool("ENABLE_CORS_RPC_PROXY", self.enable_cors_rpc_proxy)
        self.allow_insecure_public_bind = env_bool(
            "ALLOW_INSECURE_PUBLIC_BIND", self.allow_insecure_public_bind
        )
        self.redis_url = env_str("REDIS_URL", self.redis_url)
        self.redis_rate_limit_enabled = env_bool("REDIS_RATE_LIMIT", self.redis_rate_limit_enabled)
        self.rate_limit_rpm = env_int("RATE_LIMIT_RPM", self.rate_limit_rpm)
        self.rpc_api_key_required = env_bool("RPC_API_KEY_REQUIRED", self.rpc_api_key_required)
        rpc_keys = env_list("RPC_API_KEYS")
        if rpc_keys:
            self.rpc_api_keys = rpc_keys

        self.feature_nft = env_bool("FEATURE_NFT", self.feature_nft)
        self.feature_zk = env_bool("FEATURE_ZK", self.feature_zk)
        self.feature_sharding = env_bool("FEATURE_SHARDING", self.feature_sharding)
        self.feature_oracles = env_bool("FEATURE_ORACLES", self.feature_oracles)
        self.feature_wasm = env_bool("FEATURE_WASM", self.feature_wasm)
        self.feature_plasma = env_bool("FEATURE_PLASMA", self.feature_plasma)
        self.feature_lightning = env_bool("FEATURE_LIGHTNING", self.feature_lightning)
        self.feature_pq = env_bool("FEATURE_PQ", self.feature_pq)
        self.feature_mev = env_bool("FEATURE_MEV", self.feature_mev)
        self.feature_ai_agents = env_bool("FEATURE_AI_AGENTS", self.feature_ai_agents)

        peers = env_list("BOOTSTRAP_PEERS")
        if peers:
            self.bootstrap_peers = peers

        self.bridge_enabled = env_bool("BRIDGE_ENABLED", self.bridge_enabled)
        self.bridge_mode = env_str("BRIDGE_MODE", self.bridge_mode)
        self.bridge_auto_confirm_sec = env_int(
            "BRIDGE_AUTO_CONFIRM_SEC", self.bridge_auto_confirm_sec
        )
        self.bridge_require_l1_proof = env_bool(
            "BRIDGE_REQUIRE_L1_PROOF", self.bridge_require_l1_proof
        )
        self.bridge_dev_adapter_enabled = env_bool(
            "BRIDGE_DEV_ADAPTER_ENABLED", self.bridge_dev_adapter_enabled
        )
        rust_path = env_str("RUST_BRIDGE_PATH", "")
        if rust_path:
            self.rust_bridge_path = rust_path
        oracle_secret = env_str("BRIDGE_ORACLE_SECRET", "")
        if oracle_secret:
            self.bridge_oracle_secret = oracle_secret
        l1_queue = env_str("BRIDGE_L1_QUEUE_PATH", "")
        if l1_queue:
            self.bridge_l1_queue_path = l1_queue

        origins = env_list("CORS_ORIGINS")
        if origins:
            self.cors_origins = origins

        if self.is_production:
            self.require_wallet_file = env_bool("REQUIRE_WALLET_FILE", True)
            self.jwt_enforce_admin = env_bool("JWT_ENFORCE_ADMIN", True)
            self.sqlite_synchronous = env_str("SQLITE_SYNCHRONOUS", "FULL")
            self.enable_cors_rpc_proxy = env_bool("ENABLE_CORS_RPC_PROXY", False)
            self.log_json = env_bool("LOG_JSON", True)
            self.rpc_api_key_required = env_bool("RPC_API_KEY_REQUIRED", True)
            self.bridge_require_l1_proof = env_bool("BRIDGE_REQUIRE_L1_PROOF", True)
            self.feature_zk = env_bool("FEATURE_ZK", False)
            self.feature_sharding = env_bool("FEATURE_SHARDING", False)
            self.feature_oracles = env_bool("FEATURE_ORACLES", False)
            self.feature_wasm = env_bool("FEATURE_WASM", False)
            self.feature_plasma = env_bool("FEATURE_PLASMA", False)
            self.feature_lightning = env_bool("FEATURE_LIGHTNING", False)
            self.feature_pq = env_bool("FEATURE_PQ", False)
            self.feature_mev = env_bool("FEATURE_MEV", False)
            self.feature_ai_agents = env_bool("FEATURE_AI_AGENTS", False)
            if self.cors_origins == ["*"]:
                self.cors_origins = env_list("CORS_ORIGINS", [])

        return self

    def validate(self) -> List[str]:
        """Возвращает список ошибок конфигурации (пустой = OK)."""
        errors = []

        def weak_secret(value: str, min_len: int = 24) -> bool:
            from runtime.secret_utils import is_placeholder_secret
            return is_placeholder_secret(value) or len(value.strip()) < min_len

        for name, port in [
            ("rpc_port", self.rpc_port),
            ("http_port", self.http_port),
            ("p2p_port", self.p2p_port),
            ("ws_port", self.ws_port),
        ]:
            if not (1 <= port <= 65535):
                errors.append(f"{name} invalid: {port}")
        if self.deployment_mode not in ("dev", "staging", "prod"):
            errors.append(f"deployment_mode invalid: {self.deployment_mode}")
        if self.is_production and self.require_wallet_file:
            wallet = os.path.join(
                os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else "data",
                "wallet.json",
            )
            if not os.path.isfile(wallet):
                errors.append(f"prod mode requires wallet file: {wallet}")
        if self.rpc_api_key_required:
            if not self.rpc_api_keys:
                errors.append("RPC_API_KEY_REQUIRED=true but RPC_API_KEYS is empty")
            else:
                weak_keys = [k for k in self.rpc_api_keys if weak_secret(str(k))]
                if weak_keys:
                    errors.append("RPC_API_KEYS contains placeholder or weak key")
        if self.bridge_mode not in ("simulator", "rust"):
            errors.append(f"bridge_mode invalid: {self.bridge_mode}")
        if self.bridge_mode == "rust":
            resolved = self.resolve_rust_bridge_path()
            if not os.path.isfile(resolved):
                msg = f"bridge_mode=rust but binary missing: {resolved}"
                if self.is_production:
                    errors.append(msg)
        if self.is_production and self.bridge_mode == "simulator":
            errors.append("prod deployment should use bridge_mode=rust (or disable bridge)")
        if self.is_production and self.bridge_dev_adapter_enabled:
            errors.append("prod deployment forbids BRIDGE_DEV_ADAPTER_ENABLED")
        if self.is_production:
            if not self.cors_origins:
                errors.append("prod mode requires CORS_ORIGINS")
            if "*" in self.cors_origins:
                errors.append("prod mode forbids wildcard CORS_ORIGINS")
            if any(o.startswith("http://localhost") or o.startswith("http://127.") for o in self.cors_origins):
                errors.append("prod mode forbids localhost CORS_ORIGINS")
            blocked = {
                "FEATURE_ZK": self.feature_zk,
                "FEATURE_SHARDING": self.feature_sharding,
                "FEATURE_ORACLES": self.feature_oracles,
                "FEATURE_WASM": self.feature_wasm,
                "FEATURE_PLASMA": self.feature_plasma,
                "FEATURE_LIGHTNING": self.feature_lightning,
                "FEATURE_PQ": self.feature_pq,
                "FEATURE_MEV": self.feature_mev,
                "FEATURE_AI_AGENTS": self.feature_ai_agents,
            }
            enabled_blocked = [name for name, enabled in blocked.items() if enabled]
            if enabled_blocked:
                errors.append(
                    "prod deployment blocks dev/test/routing/offchain features: "
                    + ", ".join(enabled_blocked)
                )
            if not self.require_native_crypto:
                errors.append("prod mode requires ABS_REQUIRE_NATIVE_CRYPTO=true")
        if self.require_native_crypto:
            try:
                from crypto import native
                if not native.native_available():
                    errors.append("ABS_REQUIRE_NATIVE_CRYPTO=true but abs_native is unavailable")
            except Exception as e:
                errors.append(f"ABS_REQUIRE_NATIVE_CRYPTO=true but native crypto check failed: {e}")
        if self.deployment_mode != "dev" and not self.allow_insecure_public_bind:
            public_http = self.http_host in ("0.0.0.0", "::", "")
            public_rpc = self.rpc_host in ("0.0.0.0", "::", "")
            if public_http and not self.jwt_enforce_admin:
                errors.append("non-dev public HTTP bind requires JWT_ENFORCE_ADMIN=true")
            if public_rpc and not self.rpc_api_key_required:
                errors.append("non-dev public RPC bind requires RPC_API_KEY_REQUIRED=true")
            if (public_http or public_rpc) and "*" in self.cors_origins:
                errors.append("non-dev public bind forbids wildcard CORS_ORIGINS")
        if self.is_production:
            jwt_secret = os.environ.get("JWT_SECRET") or getattr(self, "jwt_secret", "")
            if not jwt_secret:
                errors.append("prod mode requires JWT_SECRET")
            elif weak_secret(jwt_secret):
                errors.append("prod JWT_SECRET is placeholder or too short")
        if self.is_production and self.bridge_enabled:
            if self.bridge_mode == "rust":
                try:
                    from bridge.health import check_rust_bridge_binary
                    bridge_status = check_rust_bridge_binary(self.resolve_rust_bridge_path())
                    if not bridge_status.get("ok"):
                        errors.append(
                            "prod bridge rust binary smoke-test failed: "
                            + str(bridge_status.get("error") or bridge_status)
                        )
                except Exception as e:
                    errors.append(f"prod bridge rust binary smoke-test failed: {e}")
            if not self.bridge_oracle_secret:
                errors.append("prod bridge requires BRIDGE_ORACLE_SECRET for relayer callbacks")
            elif weak_secret(self.bridge_oracle_secret):
                errors.append("prod BRIDGE_ORACLE_SECRET is placeholder or too short")
            l1_rpc = [
                os.environ.get("ETH_RPC_URL", "").strip(),
                os.environ.get("BSC_RPC_URL", "").strip(),
                os.environ.get("POLYGON_RPC_URL", "").strip(),
            ]
            if not any(l1_rpc):
                errors.append("prod bridge requires at least one L1 RPC URL (ETH_RPC_URL/BSC_RPC_URL/POLYGON_RPC_URL)")
            if not self.bridge_require_l1_proof:
                errors.append("prod bridge requires BRIDGE_REQUIRE_L1_PROOF=true")
        return errors

    def __repr__(self) -> str:
        return (
            f"Config(chain={self.chain_id} '{self.network_name}', "
            f"rpc=:{self.rpc_port}, http=:{self.http_port}, "
            f"p2p=:{self.p2p_port}, db='{self.db_path}')"
        )
