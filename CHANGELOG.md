# Changelog

Все значимые изменения документируются здесь. Формат основан на [Keep a Changelog](https://keepachangelog.com/).

**Текущая волна API:** `api_wave = 61` (проверка: `GET /status`)

---

## [1.2.24] — 2026-07-06

### Added

- Public testnet Docker stack: `docker-compose.testnet.yml`, seed/validator configs, `docker_testnet_seed.ps1`
- nginx TLS/rate-limit template `deploy/nginx/testnet.example.conf`
- `.env.testnet.example` for JWT/RPC keys and ports

---

## [1.2.23] — 2026-07-06

### Added

- Rocks read path for tx propagation (`get_tx_propagation_trace`, `get_recent_tx_propagation`)
- `scripts/testnet_readiness.ps1` — automated PUBLIC_TESTNET local prerequisites

---

## [1.2.22] — 2026-07-06

### Added

- `RocksEngine.state_root_from_account_prefix` — native Rocks scan + state root without Python blob round-trip
- Shared `compute_state_root_from_account_blobs` in Rust `state_trie`

### Changed

- `RocksChainStore.compute_state_root` uses native prefix scan when accumulator is cold

---

## [1.2.21] — 2026-07-06

### Added

- RocksDB storage for `nft_offers`, `nft_auctions`, and `nft_sales` (hybrid prod) + aux migrations
- Reorg invariant test: `StateRootAccumulator` / `compute_state_root` vs `live_state_root` meta

### Fixed

- `soak_monitor.ps1` — hashtable splat to `health_watch` (long soak no longer exits in 50ms); stricter pass criteria

---

## [1.2.20] — 2026-07-06

### Added

- RocksDB storage for `nft_tokens` (hybrid prod path) + aux migration

---

## [1.2.19] — 2026-07-06

### Fixed

- Prod mesh mining stuck when `request_peer_state_roots` returned fewer than 2 responses (`runtime/mesh_mining.py`)

### Added

- Rocks reorg tip metadata test; mesh mining gate unit tests

---

## [1.2.18] — 2026-07-06

### Added

- `prod_mesh_failover.ps1`, `prod_signed_tx_smoke.py`, `prod_mesh_industrial.ps1`
- `verify_p2p_ci --mode prod-mesh3-recovery`
- RocksDB `evm_logs` persistence + hybrid aux migration

### Fixed

- Mesh recovery drill: peer-count fallback when topology is `under_mesh`
- PowerShell exit codes for health_watch / industrial gate

---

## [1.2.17] — 2026-07-06

### Added

- `scripts/soak_monitor.ps1` — 24h+ prod mesh soak with JSON report
- Harness `?quick=1&peer_timeout=3` for fast monitoring polls

### Fixed

- `health_watch.ps1` — harness timeout, quick/full cycle, mesh height alignment, `failed_checks` array handling

### Changed

- `health_watch` uses quick harness by default; full peer scan every 6th cycle

---

## [1.2.16] — 2026-07-06

### Fixed

- Prod mesh followers crash-loop: `require_wallet_file` vs watch-only synced follower (height > 1)
- `docker_prod_3node.ps1/.sh`: `-KeepVolumes` auto-skips DB seed; no-seed path starts all 3 nodes together
- Prod mesh script: node2/node3 wait `/health/ready` (5 min), logs on failure

---

## [1.2.15] — 2026-07-05

### Fixed

- CI: remove unused `numpy` import in `features/postquantum.py` (test collection)
- CI: Docker prod image pushes **GHCR only** (no Docker Hub `abs-blockchain-prod:ci` 401)
- CI: `publish-wheel-on-release.yml` invalid `if: secrets.*` syntax

### Added

- `scripts/health_watch.ps1` — prod mesh poll + optional webhook

### Changed

- `MAINNET_GAP_ANALYSIS.md`, `INCIDENT_RESPONSE.md`, `REPO_PROFILE.md` — RocksDB DR, 703 tests, CI refs
- `OBSERVABILITY.md`, README — health watch docs

---

## [1.2.14] — 2026-07-05

### Added

- `docs/ARCHITECTURE.md` — honest mermaid architecture (prod vs dev paths)
- `docs/PUBLIC_TESTNET.md` — public testnet go-live checklist (not live)
- `.github/workflows/security-audit.yml` — pip-audit on `requirements.txt`

### Changed

- README: GitHub Actions CI badges (tests, docker, security), architecture section, v1.2.13 refs, 703 tests

---

## [1.2.13] — 2026-07-05

### Fixed

- Backup manifest `chain_tip` read from checkpoint copy (was silently 0)
- Verify skips strict tip match when manifest tip is 0 (unknown)

---

## [1.2.12] — 2026-07-05

### Fixed

- Docker backup: mount chain volume read-write (node1 stopped); open RocksDB read-only for checkpoint

---

## [1.2.11] — 2026-07-05

### Fixed

- Docker backup: do not `rmtree` bind-mounted `/backup` (EBUSY on Windows Docker)

---

## [1.2.10] — 2026-07-05

### Fixed

- Docker mesh backup: bind-mount script file instead of stdin pipe (PowerShell on Windows)
- Verify `backup_manifest.json` + `chainstore/` before declaring backup OK
- Resolve node1 image by ID (`docker inspect .Image`) for reliable `docker run`

---

## [1.2.9] — 2026-07-05

### Fixed

- Docker mesh backup uses `docker run` + existing node1 image/volume (no `compose run` rebuild)
- `Dockerfile.prod` — dummy `src/lib.rs` before `cargo fetch` for abs_native layer cache

---

## [1.2.8] — 2026-07-05

### Fixed

- `dr_restore_rehearsal.ps1` — explicit `-DockerMesh1` call (array splat broke switch binding on PS 5.1)
- Docker backup uses `--entrypoint python` (avoid main.py swallowing stdin pipe)

---

## [1.2.7] — 2026-07-05

### Fixed

- Docker mesh backup: stop node1 briefly + one-off checkpoint (RocksDB LOCK while node running)
- Optional `-Live` read-only checkpoint when prod image includes `read_only` RocksEngine

### Changed

- `RocksEngine` — `read_only=True` opens DB with `open_for_read_only` for live backups

---

## [1.2.6] — 2026-07-05

### Fixed

- `backup_chainstore.ps1 -DockerMesh1` — stdin-piped checkpoint backup (no `/app/scripts/` in old prod images)

### Added

- `scripts/docker_backup_in_container.py` — minimal in-container backup via `docker exec python -`

---

## [1.2.5] — 2026-07-05

### Fixed

- `scripts/dr_restore_rehearsal.ps1` — ASCII-only strings (Windows PowerShell 5.1 parse error on em-dash)

### Added

- `scripts/bench_storage_commit.py` — SQLite vs RocksDB commit latency benchmark

---

## [1.2.4] — 2026-07-05

### Added

- RocksDB tuning: `ROCKSDB_BLOCK_CACHE_MB`, `ROCKSDB_WRITE_BUFFER_MB` → native `RocksEngine`
- LSM property introspection in `get_stats()` (`rocksdb_properties`)
- `scripts/dr_restore_rehearsal.ps1` — temp restore verify without touching live data
- `RELEASE_NOTES_v1.2.3.md`

### Changed

- `docs/STORAGE_ROCKSDB.md` — aux.db permanent scope + tuning table

---

## [1.2.3] — 2026-07-05

### Added

- `docs/STORAGE_ROCKSDB.md` — honest hybrid RocksDB architecture + roadmap
- `storage/chain_backup.py` — backup/restore for Rocks chainstore and SQLite
- `scripts/backup_chainstore.py`, `restore_chainstore.py`, `backup_chainstore.ps1`
- `scripts/backup_rocks_drill.py` — CI DR drill for RocksDB
- `tests/unit/test_chain_backup.py`

### Changed

- CI: `backup_rocks_drill.py` + rocks unit tests in hybrid critical gate

---

## [1.2.2] — 2026-07-05

### Added

- `.github/workflows/docker-prod-image.yml` — BuildKit + GHA cache; publishes `ghcr.io/gruver87/abs-blockchain-node` on master/tags
- `-PullLatest` / `--pull-latest` for prod mesh scripts (uses GHCR image via `ABS_PROD_IMAGE`)
- `docs/DOCKER_IMAGES.md` — honest Docker/GHCR ops guide
- BuildKit cache layers in `Dockerfile.devnet-rust` (same pattern as prod)

### Changed

- `docker-compose.prod.3node.yml` — `ABS_PROD_IMAGE` override for prebuilt images
- Prod mesh README section — GHCR pull path documented

---

## [1.2.1] — 2026-07-05

### Added

- `GET /status` — `p2p_sync_status`, `peers_connected`, `validators_registered`, `mesh_min_peers`, `bridge_disabled_reason`
- `GET /bridge/status` — alias for bridge overview
- `scripts/probe_mesh_nodes.ps1` — multi-port mesh/bridge/features probe
- `LightClient.sync_headers_from_peers()` for untrusted peer headers
- `tests/unit/test_light_client_sync.py`

### Fixed

- Light client local bootstrap: `sync_from_blockchain()` uses trusted sequential `add_header()` (was failing peer validation on local DB → “0 headers synced”)
- Explorer dashboard: contextual P2P badges; deployment mode row; bridge off reason
- `scripts/full_audit.py`: solo/stale/under-mesh warnings instead of generic “inconsistent”
- `setup_prod_env.ps1`: explicit `BRIDGE_ENABLED=false` for mainnet-v1 cutover policy

### Docs

- README: deployment matrix, chain IDs 77777 vs 778888, test count 698, probe script
- [RELEASE_NOTES_v1.2.1.md](RELEASE_NOTES_v1.2.1.md)

---

## [1.2.0-industrial] — Wave 37–63 (июнь 2026)

### Wave 63 — Admin lockdown for node repair endpoints

- Node-admin POST endpoints (`/p2p/reconnect`, `/sync/fast-sync`, `/sync/reconcile`, `/chain/consistency/repair`, `/testnet/reorg-exercise`, `/testnet/fork-exercise`) are no longer dev-public when JWT admin enforcement is enabled
- Docker 3-node devnet now runs with `JWT_ENFORCE_ADMIN=true` and a devnet-only `JWT_SECRET`, so recovery/sync tests exercise the real admin boundary
- `verify_p2p_ci.py` automatically obtains a dev JWT from `/auth/token` and retries protected repair/recovery POSTs with `Authorization: Bearer ...`
- Unit coverage now asserts dev-admin `/sync/reconcile` rejects unauthenticated requests and accepts authenticated calls through the auth boundary
- Multi-node proof now reports manifest/evidence-backed effective validator counts and separates low-height pending checks from real failed checks
- **`api_wave` remains 61** — Wave 63 hardens access policy, not the REST API surface

### Wave 62 — Live Docker recovery gate

- `verify_p2p_ci.py --mode devnet3-recovery` — live 3-node Docker recovery drill that stops `node2`, keeps `node1/node3` consistent, restarts `node2`, and requires mesh rejoin plus matching `state_root`
- `scripts/docker_devnet_3node.ps1 -Recovery` — optional industrial gate after normal 3-node verification
- Recovery assertions verify persistent heights, root convergence, peer rejoin, and `topology_healthy=true` after restart
- **`api_wave` remains 61** — Wave 62 hardens live verification, not the REST API surface

### Wave 61 — Network hygiene + real peer rejoin

- P2P handshake now advertises each node's real listening `p2p_port`, so peer discovery/rejoin stores stable node addresses instead of ephemeral TCP socket ports
- `GET /p2p/topology` / `GET /p2p/peer-score` — live peer graph, known rejoin candidates, height gaps, last-seen ages, and topology health
- `POST /p2p/reconnect` — actively reconnect bootstrap/known peers from the unified node runtime
- `scripts/docker_devnet_3node.ps1` — host-port guard prevents local `python main.py` from being mixed with Docker devnet ports
- **`api_wave` → 61**

### Wave 60 — CI L1 RPC + relayer live e2e

- `bridge/mock_l1_rpc.py` — in-process Ethereum JSON-RPC endpoint for isolated CI
- `GET /testnet/bridge-relayer-proof` — relayer readiness dashboard
- `verify_p2p_ci.py` — `verify_bridge_relayer()` + `--mode ci-bridge-relayer`
- **`api_wave` → 60**

### Wave 59 — Bridge relayer e2e + Explorer fork UI

- `RustBridge.enqueue_l1_incoming()` — L1 incoming queue for relayer watch
- `POST /bridge2/transfer` — routes through `RustBridge` when enabled (incoming/outbound)
- `POST /bridge/oracle/l1-register` — enqueues incoming/outbound L1 queue entries
- Explorer — Testnet Fork Monitor card, `l1_tx_hash` on bridge forms, `bridge2` RustBridge path
- `verify_p2p_ci.py` — `verify_bridge()` after adversarial; `--mode ci-bridge` isolated test
- `tests/unit/test_bridge_relayer_e2e.py` — lock → queue → relayer incoming e2e
- **`api_wave` → 59**

### Wave 58 — Fork CI (partition + recovery)

- `GET/POST /testnet/fork-exercise` — fork-status before/after + P2P reconcile drill
- `verify_p2p_ci.py` — `verify_fork_recovery()` after multi-node proof
- `--mode ci-fork` — real partition test: stop follower node, mine ahead, restart, reconcile
- **`api_wave` → 58**

### Wave 57 — Real core (no random stubs in consensus path)

- **Deterministic proposer** — `ConsensusEngine` + `ValidatorSelection.select_proposer_weighted`; removed `random` fallbacks and AI-validator mining shortcut
- **Finality quorum** — `FinalityEngine` uses live validator count (not hardcoded 32)
- **Reorg finality guard** — `Blockchain.reorg_to_ancestor()` refuses rollback below finalized checkpoint
- **P2P reorg** — `ReorgPredictor.analyze_live_peers()` wired into fork reconcile
- **MEV** — fee-ordering analysis from mempool (no `random.uniform` profits)
- **Bridge honesty** — Python bridge adapter only for explicit dev/test paths; Docker uses `RustBridge`
- `GET /status` → `core_real` flags; **`api_wave` → 57**

### Wave 56 — Multi-node proof (3-validator devnet)

- `docker/validators.devnet3.json` — 3 miners + attesters; `node*.devnet3.rust.json` configs
- `GET /testnet/multi-node-proof` — mesh + harness + validators + attestations + `proof_ok`
- `POST /testnet/reorg-exercise` — canonical replay drill (`reorg_safe` flag)
- Proposer rotation threshold: `distinct_proposers >= 3` when `expected_validators >= 3` and height ≥ 12
- `verify_p2p_ci.py` — `verify_multi_node_proof()` after state harness (attestations, rotation, reorg drill)
- **`api_wave` → 56**

### Wave 55 — 5-validator devnet

- `docker-compose.devnet-5validator.yml` — 5 nodes `:8080`–`:8084`, 3 miners + 2 attesters
- `docker/validators.devnet5.json` — manifest; addresses derived at runtime (no keys on disk)
- `GET /testnet/validators` — validator set health, proposer rotation stats
- Mining proposer gate — only selected validator forges when `active_validators > 1`
- `verify_p2p_ci.py --mode devnet5`; `.\scripts\docker_devnet_5validator.ps1`
- Devnet5 sync fix — seeded-chain `dev_signer` skip, `ensure_state_at_tip` replay at tip
- **`scripts/full_audit.py`** — unified audit: syntax, Waves 52–55, secrets, mega/final, pytest, live API, P2P
- `verify_p2p_ci.py` — unique tx recipient per run (no false fail on repeat audit)

### Wave 54 — State consistency harness

- `GET /chain/consistency/harness` — tip alignment, peer roots, supply cap, mismatch audit
- `GET /testnet/state-consistency` — alias for harness on multi-node devnet
- `POST /chain/consistency/repair` — replay chain when live state drifted from tip
- `verify_p2p_ci.py` — cross-node harness check + auto-repair in devnet/ci3 modes

### Wave 53 — Fork / slashing / partition CI

- `GET /testnet/fork-status` — divergent heads, height gaps, `consensus_healthy`, slash summary
- `GET /slashing/events` — persisted slash events from SQLite
- `verify_p2p_ci.py --mode ci3` / `ci-adversarial` — isolated 3-node + double-vote slash test
- Atomic `reorg_to_ancestor` rollback; `ensure_state_at_tip()` on boot; staking catch-up only on miner

### Wave 52 — 3-node testnet (Docker)

- `docker-compose.devnet-3node.yml` — node1 `:8080`, node2 `:8081`, node3 `:8082`
- `GET /testnet/mesh` — peer heights, `mesh_healthy`, `expected_peers`
- `verify_p2p_ci.py --mode devnet3` — 3-node sync + tx on node2 **and** node3 mempools
- `.\scripts\docker_devnet_3node.ps1` — seed DB, force-recreate, CI verify
- Faucet top-up in verify when dev signer balance low

### Wave 51 — Transaction propagation (P2P)

- Full signed tx gossip + mempool pull sync (`get_mempool` / `mempool` P2P messages)
- SQLite `tx_propagation_events` — lifecycle: submit → mempool → P2P → block → receipt
- `GET /tx/trace/{hash}`, `GET /tx/propagation/recent`
- Explorer dashboard: Tx Propagation Trace
- `verify_p2p_ci.py` checks node2 mempool after `/tx/send` on node1

### Wave 50 — Strict state_root on all nodes

- `state_root_strict_p2p` (default `true`) — P2P import rejects `state_root` mismatch above baseline
- `GET /chain/state-root/status` — local root, peer comparison, policy, recent mismatches
- SQLite `state_root_mismatches` audit log; pruned on reorg
- `/sync/status` includes `state_root_strict_p2p` and policy fields

### Wave 49 — Block proposer audit log

- `block_proposer_audit` SQLite table on every confirmed block
- Backfill from historical `blocks` on node start
- `GET /chain/proposers/stats` — top proposers by block count
- `GET /chain/proposers/history` — paginated audit log (`proposer` filter)
- `GET /chain/proposer/{addr}` — proposer detail + recent blocks
- Pruned on reorg; `proposer_audit_count` in `/chain/metrics`

### Wave 48 — Address tx index + receipt backfill

- `GET /address/{addr}/activity` — balance, sent/received counts, last tx height
- `GET /address/{addr}/txs` — paginated history (`limit`, `offset`, `direction=sent|received|all`)
- Idempotent backfill: historical `transactions` → `tx_receipts` on each node start

### Wave 47 — Core L1 receipts + chain metrics

- `tx_receipts` SQLite table on every confirmed tx
- `GET /chain/metrics` — avg block time, tx/receipt counts
- `GET /tx/receipt/{hash}`, `GET /receipts/block/{height}`
- Receipts pruned on reorg (`truncate_chain_state`)

### Wave 46 — NFT SQLite persistence

- NFT tokens, offers, auctions, sales history в SQLite
- Genesis collection seed при пустой БД; mint/buy/transfer сохраняются
- `GET /nft/stats`, `nft_persisted` в `/l2/status`

### Wave 45 — Reorg predictor + dev bridge

- SQLite-история оценок реорга (`reorg_assessments`)
- Исправлены `GET /reorg/depth`, `/reorg/fork`, добавлены `/reorg/history`
- `GET /features` — `api_wave`, `l2_modules`, подсказка `bridge_dev_confirm`
- Dev: `POST /bridge/confirm-pending` и alias `/bridge/dev-confirm-pending` (без HMAC)

### Wave 44 — L2 dashboard + MEV history

- `GET /l2/status` — единый дашборд Lightning / Plasma / Will / WASM / AI
- MEV analyzer: история в SQLite, `GET /mev/history`

### Wave 43 — AI agents

- AI agents / trades в SQLite, create fee 0.01 ABS
- Plasma `submit-block`: подсказки при пустой очереди

### Wave 42 — WASM + relayer status

- WASM VM: контракты / storage / events в SQLite, deploy fee 0.01 ABS
- `GET /bridge/relayer/status` — L1 queue + pending locks

### Wave 41 — Crypto Will

- Завещания в SQLite: create блокирует L1, execute → heir, cancel → refund
- `POST /will/execute` (`force=true` в dev)

### Wave 40 — L2 persistence

- Lightning: каналы в SQLite, open/close влияет на L1 ABS
- Plasma: deposits / blocks / exits в SQLite, deposit/exit влияет на L1

### Wave 39 — Oracle registry + bridge L1 queue

- HMAC-signed oracle feeds в SQLite (`GET /oracles/feeds`, `POST /oracles/feeds/submit`)
- `POST /bridge/lock` с `l1_tx_hash` → `data/bridge_l1_queue.json`
- `GET /bridge/l1-queue`, alias `GET /oracles/l1-queue`

### Wave 37–38 — EVM hardening + P2P

- EVM: LOG, EXTCODE, SELFDESTRUCT, BLOCKHASH, CALLCODE; bytecode validator в mempool
- EVM logs в SQLite (`GET /evm/logs`)
- Sharding: cross-shard реальные переводы балансов
- Bridge: `l1_tx_hash` обязателен при `ETH_RPC_URL`
- Секреты только в `.env`, честная документация в `docs/ALL_COMMANDS.txt`

---

## Проверено локально

| Проверка | Результат |
|----------|-----------|
| `pytest tests/unit` | 217 passed, 1 skipped |
| Docker devnet 2 nodes | P2P sync, heights aligned, `state_roots_match=True` |
| Docker devnet 3 nodes | `GET /testnet/mesh`, tx on node2+node3 mempools |
| `api_wave` | 52 |
| `mega_audit.py` | 256 REST routes |

---

## Честно: что это **не** даёт

- Не production mainnet
- Не полный EVM / не Ethereum-совместимость на 100%
- Bridge / Lightning / Plasma / MEV — dev/test or analysis modules with real L1 effects where stated
- Крипто-аудит не проводился

См. [DISCLAIMER.md](DISCLAIMER.md) и **Часть 0** в [docs/ALL_COMMANDS.txt](docs/ALL_COMMANDS.txt).
