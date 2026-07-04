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

### Priority 5 — Bridge (no simulators in prod)

- [x] `BRIDGE_MODE=rust` enforced by `prod_gate.py`
- [x] Real L1 RPC (`ETH_RPC_URL`, `BSC_RPC_URL`, `POLYGON_RPC_URL`)
- [ ] PyO3 bridge helper (optional; CLI sufficient today)
- Dev-only: `bridge/mock_l1_rpc.py`, `bridge/dev_bridge_adapter.py` — **blocked in prod**

### Priority 6 — EVM execution (in progress)

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
- [ ] Full opcode dispatch in Rust (future)

### Priority 7 — Bridge hardening (future)

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
