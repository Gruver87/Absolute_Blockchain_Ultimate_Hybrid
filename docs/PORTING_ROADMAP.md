# Porting Roadmap — Hybrid Industrial Blockchain

Goal: move deterministic, CPU-bound, and consensus-critical code to **Rust/PyO3** while keeping **Python** as the orchestration layer. Each step ships with unit tests, CI gates, and a Python fallback only for dev (prod requires `ABS_REQUIRE_NATIVE_CRYPTO=true`).

## Python stays (orchestration layer)

| Module | Why Python |
|--------|------------|
| `main.py`, node lifecycle | Fast iteration, config, signals |
| `api/http.py`, `rpc/server.py` | REST/RPC routing, OpenAPI, admin gates |
| `network/p2p_node.py` | Async gossip, peer management |
| `sync/sync_engine.py` | Sync policy; calls Rust validators |
| `storage/database.py` | SQLite I/O, migrations |
| `consensus/*` adapters | PoS policy, slashing rules |
| `runtime/*`, `scripts/*` | Devnet, CI, Docker, prod gates |
| `web/explorer/` | Browser UI |

## Rust owns (industrial kernels)

| Crate | Kernels | Status |
|-------|---------|--------|
| `native/abs_native` (PyO3) | SHA-256, batch SHA-256, hash_text, block_header_hash, Merkle, state_root, secp256k1 verify, hash_chain validation | **Active** |
| `bridge/rust_bridge` (CLI) | L1 RPC proof, real ETH/BSC/Polygon confirmations | **Prod path** |

## Priority timeline

### Priority 1 — Crypto kernels ✅

- [x] `sha256`, `sha256_batch`, `double_sha256`
- [x] `merkle_root`, `generate_proof`, `verify_proof`
- [x] `state_root_from_accounts_json`
- [x] `verify_secp256k1_sha256` (+ batch)
- [x] `validate_hash_chain`
- Tests: `test_native_consensus_hash.py`, `test_state_root_native.py`

### Priority 2 — Consensus header hashing ✅ (this wave)

- [x] `hash_text`, `hash_text_batch` in Rust
- [x] `block_header_hash`, `block_header_hash_batch` in Rust
- [x] `core/block_header.py` wired to native kernels
- [x] `light/light_client.py` batch index via `BlockHeader.batch_hash`

### Priority 3 — Block import & validation ✅ (this wave)

- [x] `transaction_hash`, `transaction_hash_batch` in Rust
- [x] `block_canonical_hash_json`, `canonical_hash_json` in Rust
- [x] `core/blockchain.py` wired to native tx/block hash kernels
- [x] Batch tx signature verify on block import (`verify_transaction_signatures_batch`)
- Tests: `test_native_consensus_hash.py` golden vectors

### Priority 4 — Sync & P2P hardening ✅ (this wave)

- [x] `validate_imported_block_chain` — parent links + canonical block hash before P2P import
- [x] `validate_peer_header_chain` — SPV/light client header batch gate
- [x] `keccak256_hex` — real Ethereum Keccak-256 in Rust (not NIST SHA3-256)
- [x] `sync/sync_engine.py` wired to native imported-block validator
- [x] `light/light_client.py` rejects broken peer header chains
- [x] `parse_p2p_wire_line` / `encode_p2p_wire_message` — fail-closed wire envelope (size/UTF-8/JSON/allowlist)
- [x] `verify_attestation_secp256k1` + `hash_sorted_json` — attestation/tx hash+verify on gossip path
- [x] `network/p2p_node.py` PeerConnection send/recv wired to native wire kernels
- [x] `validate_p2p_status_payload` / `validate_p2p_attestation_payload` — gossip payload shape gates
- [x] `validate_p2p_block_announce` / `validate_p2p_state_root_request|response` — block & root gossip gates
- [x] `validate_p2p_handshake_payload` / `get_blocks` / `wire_tx` / `mempool_batch` — sync & tx gossip gates
- [x] `validate_p2p_validator_register` / `peers_list` / `get_block` / `get_block_by_hash` / `blocks_batch` — peer discovery & sync fetch gates
- [x] `validate_p2p_cross_shard_tx` / `cross_shard_ack` / `shard_migration` — distributed sharding gossip gates

### Priority 4b — Consensus selection kernels ✅

- [x] `consensus_stake_weighted_proposer` / `consensus_fisher_yates_committee`
- [x] `validator_selection_*` (proposer, weighted, committee, shuffle)
- [x] `state_engine_root_from_accounts_json`

### Priority 4c — Amount + StateEngine apply ✅

- [x] `amount_to_satoshi` / `amount_apply_delta_satoshi` / `amount_from_satoshi_float`
- [x] `state_engine_apply_transactions` — in-memory batch apply (fee burned)
- [x] `runtime/amount.py` + `execution/state_engine.py` wired to native kernels
- [x] `plan_transfer_fees` / `can_afford_transfer` — L1 fee split + affordability gate
- [x] `core/blockchain.py` validate/apply simple + EVM fee paths use native planner

### Priority 5 — Bridge (no simulators in prod)

- [x] `BRIDGE_MODE=rust` enforced by `prod_gate.py`
- [x] Real L1 RPC (`ETH_RPC_URL`, `BSC_RPC_URL`, `POLYGON_RPC_URL`)
- [ ] PyO3 bridge helper (optional; CLI sufficient today)
- Dev-only: `bridge/mock_l1_rpc.py`, `bridge/dev_bridge_adapter.py` — **blocked in prod**

### Priority 6 — EVM execution ✅

- [x] EVM SHA3 opcode → native Ethereum Keccak-256
- [x] `evm_u256_*` arithmetic/bitwise kernels in Rust
- [x] `evm_keccak256_memory` for SHA3 memory slices
- [x] Mempool `add_batch` + `verify_signatures_batch` via native secp256k1
- [x] P2P `_handle_mempool_batch` → native batch mempool ingest
- [x] CREATE / CREATE2 legacy deploy addresses in Rust (`evm_deploy_address_*`)
- [x] Optional EIP-1014 CREATE2 via `evm_create2_eip1014` + `config.evm_create2_eip1014`
- [x] EVM compare opcodes (`EQ/LT/GT/ISZERO/BYTE`) + memory/calldata kernels in Rust
- [x] Extended arithmetic opcodes (`SDIV/SMOD/ADDMOD/MULMOD/EXP/SIGNEXTEND`) + native MSTORE
- [x] Native PUSH decode (`evm_read_push`) + EXTCODECOPY memory kernel
- [x] Jumpdest bitmap + EIP-150 call gas cap + address masking in Rust
- [x] Native stack DUP/SWAP + memory slice for CALL/CREATE calldata
- [x] Native bytecode scan + gas remaining; validator sync with all interpreter opcodes
- [x] Pure-opcode segment runner (`evm_run_pure_until_host`) + interpreter host-boundary loop
- [x] Native env opcodes + SLOAD/SSTORE in pure runner (static host context)
- [x] Host bridge for BALANCE / EXTCODE* / BLOCKHASH in native pure runner
- [x] Runtime bridge for CALL / CREATE / LOG / SELFDESTRUCT via apply_host_op
- [x] `evm_run_until_halt` — full bytecode dispatch loop in Rust with runtime bridge
- [x] Inline Rust bridge callbacks via `host_context.bridge_state` / `bridge_hooks`

### Priority 7 — Bridge hardening ✅

- [x] Prod config validates rust bridge binary smoke-test (`config.validate`)
- [x] Prod requires L1 RPC URLs + `BRIDGE_REQUIRE_L1_PROOF`
- [x] Runtime bridge health in `/metrics` and API overview
- [x] Live L1 RPC reachability probe at startup (opt-in: `BRIDGE_PROBE_L1_RPC=true`)
- [x] L1 RPC health in `/health/ready`, `/metrics`, and Prometheus alerts

### Priority 8 — Operational tooling ✅

- [x] Full test entry: `scripts/test_all.ps1` / `test_all.sh`
- [x] Production stack gate: `scripts/verify_prod_stack.py`
- [x] Live prod smoke: `scripts/prod_smoke.py`
- [x] Release gate: `scripts/release_gate.ps1`
- [x] Multi-node P2P smoke: `scripts/multi_node_smoke.ps1` / `.sh`
- [x] Docker prod: node + relayer sidecar
- [x] Grafana panels for native crypto / bridge / L1 RPC metrics

### Priority 9 — Industrialization (simulators → real network) ✅

- [x] `.env.example` default `BRIDGE_MODE=rust` (simulator explicit opt-in)
- [x] Keccak fallback: no wrong `sha3_256`; require native or pycryptodome
- [x] `node.industrial.json` / `node2.industrial.json` — prod-like devnet profile
- [x] `start_two_nodes.ps1 -Industrial` — native crypto + rust bridge + no L2 demos
- [x] JSON-RPC wallet wave: `eth_accounts`, `eth_getStorageAt`, `eth_feeHistory`, MetaMask block fields
- [x] Solidity 0.8+ opcodes: `SLT`, `SAR`, `PC`, `MSIZE`, `SELFBALANCE`, `BASEFEE` (native + Python fallback)
- [x] Block/env opcodes: `GASPRICE`, `COINBASE`, `DIFFICULTY`, `EXTCODEHASH`
- [x] Cancun opcodes: `SGT`, `TLOAD`, `TSTORE`, `MCOPY` (Python + native pure runner SGT)
- [x] `evm_u256_slt` signed-compare fix (both-negative operands)
- [x] `eth_sendRawTransaction`: RLP decode (legacy + EIP-1559) + native `recover_eth_address_keccak`
- [x] Tests: `test_evm_extended_opcodes.py`, `test_eth_raw_tx.py`
- [x] Full EVM opcode coverage for Shanghai/Cancun (BLOBHASH, BLOBBASEFEE; EOF/blob tx optional)
- [x] Distributed sharding MVP: `shard_mode=distributed`, `assigned_shard_id`, separate DBs, P2P `cross_shard_tx`/`cross_shard_ack`
- [x] `node.shard0.json` / `node.shard1.json`, `scripts/start_shard_devnet.ps1`
- [x] Tests: `test_distributed_sharding.py`
- [x] Cross-shard 2PC quorum coordinator + resharding planner (`consensus/cross_shard_coordinator.py`)
- [x] Live resharding migrations: discover/apply API, P2P `shard_migration`, coordinator debit/credit
- [x] Multi-validator per-shard quorum (2/3 committee ACKs, manifest `shard_id`, `/sharding/cross-shard/quorum/{tx_id}`)
- [x] Cross-shard committee gossip ACK fan-out (`MSG_CROSS_SHARD_ACK`, relay dedup, `POST /sharding/cross-shard/ack`)
- [x] Public validator set registry: `validators.manifest.example.json`, `runtime/validator_loader.py`, `/validators/registry`, prod gate
- [x] Validator key provider interface: local wallet + external HSM/KMS HTTP signer (`VALIDATOR_KEY_PROVIDER`)
- [x] Validator AWS KMS provider (`VALIDATOR_KEY_PROVIDER=aws_kms`, `AWS_KMS_KEY_ID`)
- [x] Validator GCP KMS provider (`VALIDATOR_KEY_PROVIDER=gcp_kms`, `GCP_KMS_KEY_VERSION`)
- [x] Validator GCP Cloud HSM provider (`VALIDATOR_KEY_PROVIDER=gcp_cloudhsm`, HSM protection_level gate)
- [x] P2P catch-up hardening: `catch_up_sync` retry loop, `verify_p2p_ci` devnet preflight, live audit skip/extend
- [x] Validator AWS CloudHSM proxy (`VALIDATOR_KEY_PROVIDER=aws_cloudhsm`, `AWS_CLOUDHSM_SIGNER_URL`)
- [x] JSON-RPC `eth_getLogs` filters + `eth_sendRawTransaction` RLP
- [x] JSON-RPC polling filters: `eth_newFilter`, `eth_getFilterChanges`, `eth_getFilterLogs`, block/pending filters
- [x] JSON-RPC WebSocket subscriptions (`eth_subscribe` / `eth_unsubscribe`: newHeads, logs, newPendingTransactions)
- [x] Pre-mainnet audit runner: `scripts/pre_mainnet_audit.py` (static gate + JSON report + external checklist)
- [ ] External security audit before public mainnet (third-party firm; track via `scripts/external_audit_tracker.py`)
- [x] Mainnet gap analysis doc (`docs/MAINNET_GAP_ANALYSIS.md`)
- [x] Strict external audit gate in `mainnet_readiness.py` (default; `--no-strict-audit` for dev)
- [x] Prod EVM: `evm_require_deploy_salt`, `evm_create2_eip1014` required in prod config
- [x] Prod bridge: Solana blocked; L1 chains ethereum/bsc/polygon only in rust path
- [x] Prod `chain_id` must not be devnet default `77777` (placeholder `778888` in prod examples)
- [x] Prod smoke spawn (`verify_p2p_ci --mode prod-smoke`) + E2E prod boot test
- [x] `scripts/industrial_gate.py` — code gate without external audit blockers
- [x] CI: industrial gate + prod P2P smoke on Linux
- [x] Mainnet v1 config without bridge (`node.prod.mainnet-v1.example.json`)
- [x] State harness `canonical_state_root_source: blockchain.database`
- [x] PyO3 bridge helper CLI: `scripts/native_bridge_helper.py`
- Dev-only (keep blocked in prod): `bridge_mode=simulator`, `mock_l1_rpc`, `feature_wasm/plasma/lightning/pq/zk`

### Priority 10 — Mainnet launch 🔄

- [x] Mainnet readiness gate: `scripts/mainnet_readiness.py` / `.ps1` (prod stack + pre-mainnet audit)
- [x] Release gate `-Mainnet` flag: `scripts/release_gate.ps1 -Mainnet`
- [ ] External security audit before public mainnet (third-party firm; track via `scripts/external_audit_tracker.py`)
- [x] Mainnet gap analysis doc (`docs/MAINNET_GAP_ANALYSIS.md`)
- [x] Strict external audit gate in `mainnet_readiness.py` (default; `--no-strict-audit` for dev)
- [x] Prod EVM: `evm_require_deploy_salt`, `evm_create2_eip1014` required in prod config
- [x] Prod bridge: Solana blocked; L1 chains ethereum/bsc/polygon only in rust path
- [x] Prod `chain_id` must not be devnet default `77777` (placeholder `778888` in prod examples)
- [x] Prod smoke spawn (`verify_p2p_ci --mode prod-smoke`) + E2E prod boot test
- [x] `scripts/industrial_gate.py` — code gate without external audit blockers
- [x] CI: industrial gate + prod P2P smoke on Linux
- [x] Mainnet v1 config without bridge (`node.prod.mainnet-v1.example.json`)
- [x] State harness `canonical_state_root_source: blockchain.database`
- [x] Public mainnet genesis + validator set ceremony (`genesis_ceremony.py`, `GET /chain/genesis/ceremony`)
- [x] EIP-4844 blob transaction type in `eth_sendRawTransaction` (type 0x03 decode + verify)
- [x] EOF container rejected at deploy (`eof_container_not_supported`; full EOF VM optional)

## Process per module

1. Python tests + golden vectors first.
2. Rust implementation with identical behavior + PyO3 export.
3. CI: build wheel + targeted pytest in `check_hybrid_full`.
4. Enable in prod via `require_native_crypto: true`.
5. Monitor `/metrics` native crypto gauges.

## Safety flags

| Env / config | Effect |
|--------------|--------|
| `ABS_REQUIRE_NATIVE_CRYPTO=true` | Node fails closed without `abs_native` wheel |
| `ABS_DISABLE_NATIVE_CRYPTO=true` | Force Python fallback (dev only) |
| `BRIDGE_MODE=rust` + `BRIDGE_REQUIRE_L1_PROOF=true` | No simulator, real L1 RPC required |
| `deployment_mode=prod` | `scripts/prod_gate.py` static checks |

## What is NOT a simulator (prod-safe)

- Rust `abs_native` — real crypto, same outputs as Python reference
- Rust `rust_bridge` — real JSON-RPC to external chains
- P2P sync — real TCP mesh, Docker devnet 2/3/5 nodes
- SQLite persistence — `synchronous=FULL` in prod

## What stays dev-only (blocked in prod)

- `bridge_mode=simulator`
- `feature_zk`, `feature_lightning`, `feature_pq`, etc.
- `mock_l1_rpc`, `auto_sign` on `/tx/send`
- Post-quantum private-key helper endpoints
