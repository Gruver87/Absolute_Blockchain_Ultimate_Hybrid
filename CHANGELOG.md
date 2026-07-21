# Changelog

Все значимые изменения документируются здесь. Формат основан на [Keep a Changelog](https://keepachangelog.com/).

**Текущая волна API:** `api_wave = 61` (проверка: `GET /status`)

---

## [1.2.93] — 2026-07-21

### Hardened — API repair fail-loud, verify_p2p strict skips, cert-manager per-pod

- Harness/oracle/fork repair errors exposed + logged; peer_probe_error in harness
- verify_p2p_ci wave/bridge/prod-endpoint skips fail-closed unless VERIFY_P2P_ALLOW_SKIP=1
- docs/STATE_ROOT_ENCODING_MIGRATION.md; cert-manager per-pod example

---

## [1.2.92] — 2026-07-21

### Hardened — mining fail-loud, state_root encoding scaffold

- Mining loop: PBS/MEV/shard/epoch/light-client errors logged
- `runtime/state_root_encoding.py` — v1 active, v2 satoshi scaffold blocked
- `/status` exposes `state_root_policy.encoding`
- K8s `cert-manager-p2p.example.yaml`; industrial_gate mining log checks

---

## [1.2.91] — 2026-07-21

### Hardened — P2P ops fail-loud, K8s TLS mesh, CI skip policy

- P2P: propagation/connect/status errors logged; `ops_errors` in `/status` `p2p_hardening`
- K8s: Redis init wait, `abs-p2p-tls` mount, ordinal TLS in entrypoint; configmap JSON synced
- `verify_p2p_ci`: prod-smoke/mesh3 native skip fail-closed unless `VERIFY_P2P_ALLOW_SKIP=1`
- Tests: `test_p2p_ops_errors.py`, `test_verify_p2p_skip_policy.py`

---

## [1.2.90] — 2026-07-21

### Hardened — status honesty + mesh Redis validate

- GET /status: honest core_real, rate_limit_backend, p2p_hardening
- Prod mesh Config.validate requires Redis RL + URL
- K8s Redis probes + TLS/Redis on node.prod.k8s.json; k8s_prod_gate extended

### Fail-loud

- ChainStorage backup, WebSocket send, consensus parallel add_block, bridge oracle

### Docs / tests

- [RELEASE_NOTES_v1.2.90.md](RELEASE_NOTES_v1.2.90.md)

---

## [1.2.89] — 2026-07-21

### Hardened — mesh Redis + auth + honesty

- Prod 3-node compose: Redis service + REDIS_RATE_LIMIT/URL on all nodes; prod_gate enforces
- JWT secret lazy from env; Redis RL fail-closed by default + mid-flight deny
- Bridge/Casper/Beacon API honesty; repair sync_error; mining/P2P/hybrid silent-fail purge
- full_audit solo P2P fail-closed; handshake identity reject test

### Docs

- [RELEASE_NOTES_v1.2.89.md](RELEASE_NOTES_v1.2.89.md)

---

## [1.2.88] — 2026-07-21

### Hardened — soak / rate limit / TLS

- health_watch fail-exit on hard FAIL; soak/industrial_gate require wall-clock hours
- Prod Redis RL: no memory fallback; honest backend logging
- Single-node `docker-compose.prod.p2ptls.yml` + `docker_prod.ps1 -P2pTls`
- Mining path: log peer-root / sync schedule failures (prod clears consistency)

### Docs / tests

- SECURITY.md P2P TLS + Redis; mint_admin_jwt + prod TLS tests
- [RELEASE_NOTES_v1.2.88.md](RELEASE_NOTES_v1.2.88.md)

---

## [1.2.87] — 2026-07-21

### Hardened — P2P

- TLS enabled ⇒ always `CERT_REQUIRED` (removed `CERT_NONE` path)
- Handshake `node_id` cryptographically bound to peer cert CN/SAN
- Optional `P2P_TLS_PEER_FINGERPRINTS` allowlist; richer `/p2p/security` tls block
- Prod gate: TLS+mTLS required on **all** prod profiles (not only mesh)

### Hardened — Auth / API / config

- JWT admin requires `role=admin`; `scripts/mint_admin_jwt.py` for prod ops
- Constant-time RPC API key verify; GET rate-limited
- `bridge_enabled` default false; prod forces wallet + TLS bind/fail-closed
- Genesis strict default in prod; PBS behind `feature_mev`; slash honesty fields

### Hardened — L1 bridge tooling (bridge remains OFF)

- Atomic `save_l1_queue`; fail-loud `get_contract_code` on RPC errors
- Cutover: relayer / L1 probe exceptions → errors
- API honesty: Solana marked dev-only; rust stderr logged

### Docs

- [docs/P2P_TLS.md](docs/P2P_TLS.md), [docs/BRIDGE_L1_MAINNET.md](docs/BRIDGE_L1_MAINNET.md), [RELEASE_NOTES_v1.2.87.md](RELEASE_NOTES_v1.2.87.md), [SECURITY.md](SECURITY.md)

---

## [1.2.86] — 2026-07-21

### Fixed / hardened

- **Prod Config:** pply_env / alidate cannot weaken signatures, proposer, peer state_root, JWT admin, RPC keys; forbid RATE_LIMIT_RPM=0 and ALLOW_INSECURE_PUBLIC_BIND
- **Slash persist / callback:** fail-loud (no silent swallow)
- **Rate limiter:** prod requires working limiter; Redis errors fail-closed when Redis RL enabled; RPC auth ImportError fails start when required
- **Compose:** mem_limit/cpus + log rotation on prod + prod.3node
- **External audit tracker:** human items need real note + http(s) evidence URL (rejects template stubs)
- **industrial_gate:** TLS warning reads prod mesh JSON (was dead on bare Config())

### Changed

- **docker_prod_3node.ps1:** TLS+mTLS overlay **default** (-NoP2pTls to opt out)
- Mesh JSON + compose overlay: P2P_TLS_REQUIRE_CLIENT_CERT=true
- Threat model documented in docs/P2P_TLS.md

### Evidence / docs

- Bridge decision **OFF** recorded for mainnet-v1 / pre-audit until audited L1 contracts
- Soak checkbox synced; float tip-root known-limitation stamp for auditors

### Notes

- Prepares stack for **external audit engagement**; does **not** claim audit complete or public mainnet

---

## [1.2.85] — 2026-07-21

### Proven (ops)

- **48h prod mesh soak PASS** (2026-07-19 07:02 → 2026-07-21 07:03): `fail_lines=0`, `hours_requested=48`
- `industrial_gate --min-soak-hours 48` OK · `testnet_readiness -MinSoakHours 48` OK
- Strict pre-rescore report kept (`mesh_warn=11`, all height delta ≤1); rescored `passed=true`

### Added / changed

- **`docker-compose.prod.3node.yml`**: json-file log rotation `50m` × `3` (soak-safe vs Docker VM disk fill)
- **`health_watch.ps1`**: mesh align allows height delta ≤1; tip hash check only when heights equal
- **`soak_monitor.ps1`**: `-RescoreOnly`, transient mesh-warn policy, UTF-8 report without BOM
- Docs / README / REPO_PROFILE: honest 48h PASS status

### Notes

- Local soak artifacts under `logs/` remain gitignored
- Still **not** a launched public mainnet; external audit / public VPS / bridge cutover remain open

---

## [1.2.84] — 2026-07-17

### Fixed / hardened

- **Mining sync probe:** log + clear `_state_consistent` on `sync_state` failure (no silent pass)
- **SyncEngine:** log wire state_root probe failures; expose `wire_probe_ok` in status
- **Genesis meta:** fail-loud in prod on `set_meta` write failure
- **State-root mismatch audit:** log when `record_state_root_mismatch` fails
- **API `/chain/state-root/status`:** return `peer_probe_error` instead of looking like 0 peers OK
- **IMS reconcile:** `fail_loud` for nonce mirror errors in prod
- **prod_gate:** forbid `allow_state_root_rewrite=true`; mesh1 peers≥1; mesh2/3 `follower_genesis_sync`
- **industrial_gate:** `_check_fail_loud_surfaces` static freeze

### Added

- `tests/unit/test_silent_except_honesty.py`

### Notes

- Live 48h soak mesh is **not** restarted by this release
- Tip float `"b"` encoding and float `balance` column unchanged

---

## [1.2.83] — 2026-07-17

### Fixed / hardened

- **IMS:** post-block `reconcile_from_store` from DB satoshi (fees/rewards/burns); seed fail-loud in prod
- **API `/state/*`:** DB cross-check + `canonical` flag; `/state/supply` prefers DB; `/state/credit` blocked in prod
- **`get_address_activity` / `PersistentStorage.get_account_state` / Rocks+SQLite `get_total_supply`:** prefer satoshi
- **`Blockchain` funds check:** compare in satoshi
- **`industrial_gate`:** freeze tip float `"b"` soak contract + IMS reconcile surface

### Added

- `tests/unit/test_ims_reconcile_honesty.py`

### Notes

- Live 48h soak mesh is **not** restarted by this release
- Tip `compute_db_state_root` float `"b"` encoding unchanged
- Float ABS column still retained

---

## [1.2.82] — 2026-07-17

### Fixed

- **SQLite genesis reset** (`_reset_accounts_from_alloc_locked`): dual-write `balance_satoshi`
- **`nonce_increment`**: INSERT includes `balance_satoshi=0` (match `increment_nonce`)
- **`DatabaseStateAdapter`**: `get_balance_satoshi` via `canonical_balance_satoshi` (no float×1e6)
- **`migrate_sqlite_to_rocks`**: preserve `balance_satoshi` when present
- **`PersistentStorage.update_balance`**: delegate to DB dual-write (no accidental nonce bump)

### Added

- `tests/unit/test_balance_write_path_unify.py`
- `industrial_gate` checks reset_accounts + adapter satoshi path

### Notes

- Live 48h soak mesh is **not** restarted by this release
- Tip `compute_db_state_root` float `"b"` encoding unchanged (soak contract)
- Float ABS column still retained

---

## [1.2.81] — 2026-07-17

### Changed

- **StateEngine:** account balances stored as integer satoshi; genesis/tx wire still ABS via `runtime.amount`
- **`compute_state_engine_root`:** payload uses `balance_satoshi`
- **`Blockchain.get_balance` / `get_balance_satoshi`:** via `runtime.state_truth` (prefer satoshi dual-write)
- **`industrial_gate`:** StateEngine + `canonical_balance_satoshi` surface check

### Added

- `runtime/state_truth.py`
- `tests/unit/test_state_engine_satoshi.py`

### Notes

- Live 48h soak mesh is **not** restarted by this release
- Tip consensus root remains DB/Rocks; StateEngine is auxiliary deterministic sandbox
- Float ABS column still retained for compatibility

---

## [1.2.80] — 2026-07-17

### Changed

- **Money path:** dual-write `balance_satoshi` (INTEGER) alongside float `balance` on SQLite + Rocks account rows; reads prefer satoshi
- **`runtime/amount.py`:** `dual_write_balance`, `account_satoshi`, `apply_delta_satoshi`
- **`industrial_gate`:** `_check_balance_precision` static surface

### Added

- `tests/unit/test_balance_satoshi_dual_write.py`

### Notes

- Live 48h soak mesh is **not** restarted by this release; new dual-write applies on next node image rebuild
- Float ABS column retained for compatibility — not yet dropped

---

## [1.2.79] — 2026-07-17

### Fixed / hardened (core доводка — no new features)

- **Docs:** NFT/EVM logs on prod hybrid are RocksDB (not SQLite-only); ARCHITECTURE + MAINNET_GAP + README aligned with STORAGE_ROCKSDB
- **IMS sync:** `except: pass` on ImmutableState apply → fail-loud in prod
- **PS1:** remaining Unicode em-dashes scrubbed in `scripts/*.ps1`
- **State root:** prod refuses tip header `state_root`/`hash` rewrite (`allow_state_root_rewrite=false`); genesis h=0 still alignable
- **Consensus:** prod `consensus_mode=unified` skips parallel Casper/Beacon/LMD/standalone engines in `main.py` (adapter already unified)
- **Amounts:** `runtime/amount.py` shared satoshi helpers; IMS + tx_validator import them
- **EVM:** unsalted CREATE address deterministic (no `time.time()`); CREATE2 EIP-1014 path unchanged and tested

### Added

- `tests/unit/test_amount_units.py`, `test_state_root_rewrite_guard.py`, `test_evm_create_address.py`

---

## [1.2.78] — 2026-07-17

### Added

- **`scripts/export_audit_pack.py`** / **`.ps1`** — soak-safe static audit pack (gates, docs, soak artifacts, zip + `manifest.json`); never restarts prod mesh
- **`external_audit_tracker`** — `-SyncAutomated` / `-ShowAutomated`, `--evidence-url` / `--evidence-note` on `--set`
- **`tests/unit/test_export_audit_pack.py`**

### Fixed

- **`prepare_48h_soak.ps1`** — PowerShell parse error from Unicode em-dash
- **Ops PS1 strings** — ASCII hyphens in `bridge_cutover_evidence_suite`, `docker_devnet`, `reset_genesis`, `setup_prod_env`

### Changed

- **`industrial_gate.ps1`** — forwards `-MinSoakHours`, `-CeremonyDir`, `-RequireCeremonyPin`, `-Json`
- **`restart_soak_prod_mesh.ps1`** — default log `logs/soak_48h_v1.2.77.log`
- **Docs** — honest 48h soak status (RUNNING since 2026-07-17, not PASS); EVIDENCE_MATRIX, MAINNET_GAP, PUBLIC_TESTNET, REPO_PROFILE

---

## [1.2.77] — 2026-07-14

### Fixed

- **P2P rate limit** — exempt `new_block`, `get_block`, `get_blocks`, `new_tx`, and mempool sync types from per-peer 500/s throttle so prod mesh catch-up no longer drops consensus traffic from the leader (`docker-prod-mesh-1`)

### Changed

- **`scripts/industrial_gate.py`** — stricter check that sync wire types stay rate-limit exempt
- **`tests/unit/test_p2p_industrial.py`** — expanded sync exempt coverage

---

## [1.2.76] — 2026-07-14

### Fixed

- **`docker_prod_3node.ps1`** — PowerShell parse error (Unicode em-dash in TLS verify catch block)
- **`gen_p2p_mesh_tls.py`** — Windows fallback via `cryptography` when `openssl` absent; also probes Git for Windows `openssl.exe`

### Added

- **`scripts/p2p_tls_crypto.py`** — pure-Python CA/node cert generation
- **`tests/unit/test_p2p_tls_crypto.py`**
- **`prod_mesh_resilience_suite.ps1`** — preflight hint when mesh unreachable (e.g. placeholder `RPC_API_KEYS`)

### Changed

- **`docs/P2P_TLS.md`** — Windows TLS generation note

---

## [1.2.75] — 2026-07-14

### Added

- **`scripts/verify_p2p_tls_mesh.py`** — static cert + live `/p2p/security.tls` verify for prod mesh
- **`scripts/p2p_tls_preflight.py`** + **`prepare_p2p_tls_mesh.ps1`** — TLS material preflight
- **`scripts/p2p_tls_evidence_suite.ps1`** — gen/start/verify TLS mesh + optional failover drill
- **`scripts/docker_prod_3node_p2ptls.ps1`**, **`probe_p2p_tls_mesh.ps1`**
- **`soak_preflight.py --require-p2p-tls`**, **`prepare_48h_soak.ps1 -RequireP2pTls`**
- **`monolith_gate.py --p2p-tls-preflight`** / **`--p2p-tls-live`**
- **`tests/unit/test_verify_p2p_tls_mesh.py`**

### Changed

- **`prod_mesh_resilience_suite.ps1`** — `-P2pTls` runs TLS verify after mesh probe
- **`verify_prod_mesh_probe.py`** — records `p2p_tls_enabled` / `p2p_tls_ready` in deep probe
- **`docs/P2P_TLS.md`** — evidence suite, soak, monolith gate workflow

---

## [1.2.74] — 2026-07-14

### Added

- **`scripts/verify_prod_mesh_probe.py`** + **`probe_prod_mesh.ps1`** — structured prod mesh verify (`:18180-:18182`, chain 778888)
- **`scripts/prod_mesh_resilience_suite.ps1`** — probe + stabilize + failover + optional DR rehearsal (no soak)
- **`scripts/ceremony_evidence_suite.ps1`** + **`prepare_ceremony_deploy.ps1`** — genesis ceremony preflight path
- **`tests/unit/test_verify_prod_mesh_probe.py`**

### Changed

- **`docs/GENESIS_CEREMONY.md`**, **`docs/EVIDENCE_MATRIX.md`**, **`docs/MAINNET_GAP_ANALYSIS.md`**, **`docs/PUBLIC_TESTNET.md`**

---

## [1.2.73] — 2026-07-14

### Added

- **`scripts/bridge_cutover_evidence_suite.ps1`** — unified bridge L1 cutover path (`-RpcOnly` / `-Full` / `-Live`)
- **`scripts/prepare_bridge_l1_cutover.ps1`** — wrapper for cutover evidence suite
- **`.env.bridge.cutover.example`** — L1 RPC + contract env template for prod cutover
- **`scripts/testnet_backup_restore.ps1`** — Docker testnet seed backup + optional DR rehearsal
- **`scripts/testnet_log_rotate.sh`** — rotate `data/node.log` inside testnet containers (VPS cron)
- **`tests/unit/test_bridge_cutover_evidence.py`**

### Changed

- **`docs/BRIDGE_L1_MAINNET.md`** — evidence suite workflow
- **`docs/VPS_DEPLOY.md`**, **`docs/PUBLIC_TESTNET.md`** — backup/restore + log rotation checklist
- **`bridge_l1_cutover.py`** — hint for evidence suite on placeholder contract failures

---

## [1.2.72] — 2026-07-14

### Added

- **`scripts/testnet_dns_cutover.py`** — DNS resolve + HTTPS `/api` probe before public cutover
- **`scripts/prepare_testnet_dns_cutover.ps1`** — workstation wrapper for DNS/TLS verification
- **`scripts/vps_testnet_bootstrap_mesh3.sh`** — Linux VPS 3-node testnet mesh bootstrap
- **`vps_testnet_preflight.py --mesh3` / `--domain`** — mesh3 deploy steps + optional HTTPS cutover probe
- **`tests/unit/test_testnet_dns_cutover.py`**

### Changed

- **`vps_testnet_bootstrap.sh`** — optional `--mesh3` / `MESH3=1` for validator overlay
- **`deploy/nginx/testnet.example.conf`** — port 80 ACME + HTTPS redirect for certbot
- **`prepare_vps_testnet.ps1`** — `-Mesh3`, `-Domain` flags
- **`docs/VPS_DEPLOY.md`**, **`docs/PUBLIC_TESTNET.md`** — VPS mesh3 + DNS cutover path

---

## [1.2.71] — 2026-07-14

### Added

- **3-node public testnet mesh** — `docker-compose.testnet.mesh3.yml`, `docker/node.testnet.validator3.json`, ports `:19082/:19088/:19502`
- **`scripts/docker_testnet_mesh3.ps1`** — start seed + 2 validators and verify sync
- **`scripts/testnet_health_watch.ps1`** — periodic mesh health polling (`-Mesh2` / `-Mesh3`)
- **`verify_testnet_mesh.py --mesh3`** — 3-node verify (`:19080/:19081/:19082`)
- **`probe_testnet_mesh.ps1 -Mesh3`**, **`docker_testnet_seed.ps1 -Mesh3`**
- **`public_testnet_gate.py --mesh3`**, **`testnet_evidence_suite.ps1 -Mesh3`**
- **`TESTNET_EXPECTED_PEERS`** env override in `runtime/config.py` (seed expects 2 peers in mesh3 overlay)

### Changed

- **`.env.testnet.example`** — validator-3 port vars (`TESTNET_HTTP_PORT_3`, RPC, P2P)
- **`docs/PUBLIC_TESTNET.md`** — 3-node mesh + health watch checklist

---

## [1.2.70] — 2026-07-14

### Added

- **`scripts/verify_testnet_mesh.py`** — 2-node public testnet mesh verify (seed :19080 + validator :19081, `/testnet/mesh`)
- **`scripts/docker_testnet_mesh.ps1`** — start seed+validator and verify sync
- **`scripts/probe_testnet_mesh.ps1`** — quick port probe for testnet mesh
- **`public_testnet_gate.py --mesh`** — optional 2-node mesh check in live gate
- **`tests/unit/test_verify_testnet_mesh.py`**

### Changed

- **`docker/node.testnet.seed.json`** / **validator** — `testnet_expected_peers: 1` for 2-node mesh health
- **`testnet_evidence_suite.ps1`** — mesh verify when `-WithValidator`

---

## [1.2.69] — 2026-07-14

### Added

- **`scripts/testnet_uptime_probe.py`** + **`.ps1`** — cron-friendly testnet health snapshot (`logs/testnet_uptime.json`, optional `--append` jsonl)
- **`deploy/nginx/install_testnet_nginx.sh`** — VPS nginx site installer with domain substitution
- **`monolith_gate --vps-testnet-preflight`** / **`-VpsTestnetLive`**
- **`tests/unit/test_testnet_uptime_probe.py`**

### Changed

- **`testnet_evidence_suite.ps1`** — full path: seed → public gate → VPS preflight → uptime probe
- **`testnet_readiness.ps1 -VpsPreflight`** — optional VPS preflight step
- **`docker-compose.testnet.yml`** — validator host ports `19081/19087/19501` (was `9081/9087/9501`)
- **`.env.testnet.example`** — validator port vars
- **`vps_testnet_bootstrap.sh`** — live preflight + uptime probe after seed boot
- **`docs/PUBLIC_TESTNET.md`**, **`docs/VPS_DEPLOY.md`**

---

## [1.2.68] — 2026-07-14

### Added

- **`--probe-l1-rpc-only`** — validate `ETH_RPC_URL` before L1 contracts are deployed (placeholder contracts → WARN, not FAIL)
- **`scripts/vps_testnet_preflight.py`** + **`prepare_vps_testnet.ps1`** — VPS public testnet preflight (nginx template, env, public gate)
- **`tests/unit/test_vps_testnet_preflight.py`**

### Changed

- Bridge cutover gates print hint when contracts are still placeholder
- **`public_testnet_gate.py`** default live URL `:19080` (was `:9080`)
- **`docs/BRIDGE_L1_MAINNET.md`**, **`docs/PUBLIC_TESTNET.md`** — rpc-only vs full probe workflow

---

## [1.2.67] — 2026-07-14

### Added

- **`scripts/bridge_l1_live_probe.py`** + **`bridge_l1_live_probe.ps1`** — unified L1 bridge probe (`static` / `--probe-l1` / `--live` / `--full`); writes `logs/bridge_l1_live_probe.json`
- **`--probe-l1`** and **`--bridge-live`** on `mainnet_readiness.py`, `industrial_gate.py`, `monolith_gate.py`, `verify_prod_stack.py`
- PowerShell: `industrial_gate.ps1 -BridgeCutover -ProbeL1`, `monolith_gate.ps1 -BridgeCutover -ProbeL1 -BridgeLive`
- **`tests/unit/test_bridge_l1_live_probe.py`**

### Changed

- **`bridge_l1_cutover.py`** — includes `l1_rpc` probe summary in gate meta when `--probe-l1`
- **`mainnet_readiness.py`** — `--probe-l1` works without `--live` (fixes prior `probe_l1=live` coupling)
- **`docs/BRIDGE_L1_MAINNET.md`** — live probe workflow

---

## [1.2.66] — 2026-07-13

### Added

- **`scripts/gen_p2p_mesh_tls.py`** — generate CA + node1/node2/node3 P2P TLS material for prod Docker mesh
- **`docker-compose.prod.3node.p2ptls.yml`** — compose overlay with `/app/p2p_tls` mounts and `P2P_TLS_*` env
- **`docker_prod_3node.ps1 -P2pTls`** — auto-generate certs, start mesh with TLS overlay, verify `/p2p/security.tls.ready`
- **`tests/unit/test_gen_p2p_mesh_tls.py`**

### Changed

- **`docs/P2P_TLS.md`** — Docker prod mesh TLS section

---

## [1.2.65] — 2026-07-13

### Added

- **`scripts/soak_preflight.py`** — prod mesh readiness for 48h soak (health, P2P security, harness, topology); writes `logs/soak_preflight.json`; does **not** start soak
- **`scripts/prepare_48h_soak.ps1`** — PowerShell wrapper for preflight
- **`monolith_gate.py --soak-preflight`** and **`monolith_gate.ps1 -SoakPreflight`**
- **`tests/unit/test_soak_preflight.py`**

### Changed

- **`restart_soak_prod_mesh.ps1`** — dynamic `git describe` tag in evidence + soak metadata; preflight hint in output
- **`verify_prod_stack.py --live-prod-mesh`** — P2P security policy check on all three nodes

---

## [1.2.64] — 2026-07-13

### Added

- **Optional P2P wire TLS** — `network/p2p_tls.py`, config/env `P2P_TLS_*`, fail-closed start when enabled but misconfigured
- **`scripts/gen_p2p_dev_tls.py`** — dev CA + node cert generator (OpenSSL)
- **`docs/P2P_TLS.md`** — P2P TLS vs nginx HTTP TLS
- **`GET /p2p/security.tls`** — readiness block

### Changed

- Industrial gate warns when prod profile runs with `p2p_tls_enabled=false`

---

## [1.2.63] — 2026-07-13

### Added

- **`prod-mesh3-ci-recovery`** — isolated ceremony spawn on `:15280–15282` + node2 SIGTERM/rejoin drill (GitHub Actions Linux)
- **`verify_spawn_mesh3_recovery()`** — process-based failover for CI (mirrors Docker `prod-mesh3-recovery`)
- **`verify_p2p_ci.py --recovery`** — append failover drill to `--mode prod-mesh3`

### Changed

- CI workflow: prod mesh3 step now runs spawn + recovery (55 min timeout)
- `verify_mesh3_recovery` accepts custom `stop_node2` / `start_node2` callbacks

---

## [1.2.62] — 2026-07-13

### Added

- **Rate-limit exempt wire types** — `block`, `blocks`, `status`, handshake/ping/state-root not counted (safe sync bursts on prod hub)
- **`industrial_gate` P2P hardening check** — static allowlist, security surface, config defaults
- **`verify_pair`** runs `verify_p2p_security_mesh` (2-node devnet + CI)

### Changed

- P2P maintenance clears strike counters for disconnected peers
- `/p2p/security` reports `rate_limit_exempt_types` count

---

## [1.2.61] — 2026-07-13

### Added

- **Handshake chain_id mismatch → strike/ban** — wrong-network peers accumulate strikes; `handshake_rejects` in `/p2p/security`
- **`docker_prod_3node.ps1 -RecoveryDrill`** — runs `prod-mesh3-recovery` after mesh boot
- **Recovery drill** now validates P2P security on all nodes after node2 rejoin

### Fixed

- **Rate limit no longer bans peers** — excess messages are dropped only (sync bursts were false-banning prod hub)
- **Wire EOF/parse close** — disconnect without strike/ban on peer close (fixes prod mesh split)

### Changed

- `probe_mesh_nodes.ps1 -Deep` shows `hs_rejects` from topology security
- `GET /status.p2p_summary.security` includes `handshake_rejects`

---

## [1.2.60] — 2026-07-13

### Fixed

- **`probe_mesh_nodes.ps1`** — PowerShell parse error from UTF-8 em dash; `-Deep` also tries `/p2p/security` when topology lacks `security`
- **`verify_p2p_security_mesh`** — fallback to `/p2p/topology.security` on 404; WARN (not FAIL) when `status.p2p_summary` missing on older nodes; rebuild hint for prod mesh

---

## [1.2.59] — 2026-07-13

### Added

- **P2P `_maintenance_loop`** — periodic stale/unhealthy peer eviction and ban expiry
- **`GET /status.monolith_summary`** — compact readiness snapshot (P2P, consensus, native crypto, bridge)

---

## [1.2.58] — 2026-07-13

### Added

- **`GET /status.p2p_summary`** — compact mesh health + security snapshot (peer scores, bans, rate limits)
- **`verify_p2p_security_mesh()`** in `verify_p2p_ci.py` — validates `/p2p/security` and status summary on all mesh nodes

### Changed

- `verify_n_nodes` / `verify_prod_post_checks` run P2P security checks before pass

---

## [1.2.57] — 2026-07-13

### Added

- **P2P security layer:** temporary peer bans after repeated wire abuse (`p2p_ban_seconds`, `p2p_rate_limit_strikes`)
- **Wire type allowlist:** reject unknown P2P message types with strike/ban
- **Low-score peer eviction:** `p2p_evict_min_score` drops unhealthy peers when alternatives exist
- **`GET /p2p/security`** — rate limits, active bans, eviction policy (also embedded in `/p2p/topology.security`)
- Env overrides: `P2P_BAN_SECONDS`, `P2P_RATE_LIMIT_STRIKES`, `P2P_EVICT_MIN_SCORE`, `P2P_MAX_MESSAGES_PER_SEC`

### Changed

- `probe_mesh_nodes.ps1 -Deep` prints P2P security summary from topology

---

## [1.2.56] — 2026-07-13

### Added

- **`scripts/monolith_gate.py`** — unified static gate: industrial + mainnet readiness + launch checklist → `data/monolith_gate.json`
- **`scripts/monolith_gate.ps1`** — PowerShell wrapper
- **P2P rate limit:** `p2p_max_messages_per_sec` (default 500) per-peer wire throttle

### Changed

- `test_blockchain_full` uses monolith gate instead of separate industrial/bridge preflight steps
- `industrial_gate` forwards `bridge_cutover` / `live_prod_mesh` / `strict_audit` to mainnet readiness
- CI: monolith static gate step on Python 3.12

---

## [1.2.55] — 2026-07-13

### Fixed

- **P2P auto mode:** `-P2P` / `--prefer-devnet` no longer hijacks live prod mesh on `:18180–:18182`; use `--prefer-prod-mesh` or `-ProdMesh` for prod checks
- **Harness timeouts:** `verify_p2p_ci` uses `_consistency_harness()` with `quick=1` and ≥45s HTTP timeout on prod ports (fixes false `node1 harness: timed out`)

---

## [1.2.54] — 2026-07-13

### Added

- **`-ProdMeshFull`** on `test_blockchain_full.ps1` — after `-ProdMesh` gates runs `prod_evidence_suite` (stabilize, health, failover drill, signed tx, EVM smoke)
- **`scripts/prod_mesh_full.ps1`** — one-command alias for full prod mesh ops proof
- **`prod_evidence_suite.ps1`** — `-FailoverWaitSec` parameter (passed to `prod_mesh_failover.ps1`)

### Tests

- `tests/unit/test_prod_mesh_full_gate.py`

---

## [1.2.53] — 2026-07-13

### Added

- **`-ProdMesh` / `-ProdMeshSpawn`** on `test_blockchain_full.ps1` — live prod 3-node P2P gate (`prod-mesh3-live`) + deep mesh probe + `mainnet_readiness --live-prod-mesh`
- **P2P industrial hardening:** max wire message size (`p2p_max_message_bytes`), peer health scores in topology/`/p2p/peer-score`
- **`verify_p2p_ci --mode auto`** now detects prod mesh on `:18180–:18182` before devnet
- **`probe_mesh_nodes.ps1 -Deep`** — topology + consistency harness summary (auto on `-ProdMesh`)

### Tests

- `tests/unit/test_p2p_industrial.py` — oversized message drop, auto prod-mesh detection

---

## [1.2.52] — 2026-07-13

### Added

- **Full blockchain test script:** `scripts/test_blockchain_full.ps1` / `.sh` now runs industrial gate, mainnet readiness (`--bridge-cutover`), bridge L1 cutover + preflight (static)
- **`check_everything.ps1`** delegates to `test_blockchain_full.ps1 -SkipNativeBuild` (single entry point)
- Unit tests: `tests/unit/test_l1_rpc_contract.py` for `eth_getCode` helper

---

## [1.2.51] — 2026-07-13

### Added

- **Bridge cutover (probe/live):** verify L1 contracts are actually deployed by calling `eth_getCode` for `BRIDGE_L1_LOCK_CONTRACT` and `BRIDGE_L1_MINT_CONTRACT` (fails closed on empty bytecode)

### Fixed

- **SQLite migration:** legacy `accounts` table now auto-adds `code` and `storage` columns to support state-root/account export on older DBs

---

## [1.2.43] — 2026-07-13

### Fixed

- **Rocks reorg:** purge EVM logs and tx propagation indexes above truncated height (fork safety on prod mesh)
- **External audit:** penetration test + third-party audit cannot be marked done with `auto:` notes only
- **Industrial gate:** smoke-test `abs_bridge_bin` when binary is present
- **Prod gate:** `node.prod.mainnet-v1.example.json` must keep `bridge_enabled=false` until L1 contracts

### Notes

- Bridge outbound without `l1_tx_hash` still uses ABS-side receipt hash + L1 queue (async relayer path); L1 contracts remain future cutover work
- 48h soak artifact still required for full mainnet readiness (`--min-soak-hours 48`)

---

## [1.2.42] — 2026-07-13

### Added

- **Lightning**: HTLC add/settle/refund, signed channel states (`features/l2_crypto`), BFS routing, SQLite tables `lightning_htlcs` / `lightning_channel_states`
- **Plasma**: native Merkle roots + inclusion proofs, signed L2 txs, L1 root metadata
- **WASM**: `wasmtime` engine with host `storage_get` / `storage_set` ABI (`features/wasm_engine.py`)
- **Oracles**: reporter submissions + median quorum aggregation (`oracle_reports` table)
- **ZK**: fixed balance proof verification; `create_zk_transaction` API compatibility
- HTTP: `/lightning/htlc/*`, `/lightning/route`, `/plasma/proof`, `/oracles/reports/submit`, `/oracles/aggregate`
- Tests: `tests/unit/test_l2_advanced_features.py` (29 tests pass in L2/ZK/WASM suite)

### Notes

- Advanced L2 modules are **functional + persisted** but remain **R&D** until independent audit. See `RELEASE_NOTES_v1.2.42.md`.

---

## [1.2.41] — 2026-07-13

### Added

- `scripts/mesh_heal_fork.ps1` — reseed node1 chainstore from node2 when hub diverges
- `mesh_recover.ps1 -HealFork` shortcut
- Stabilize auto-heal node1 fork (`ABS_STABILIZE_AUTO_HEAL=0` to disable)
- Post-forge mesh hold: hub waits for wire peer confirmation before next block

### Changed

- Mesh mining gate fail-closed (no solo forge on `state_consistent` alone)
- P2P STATUS echo + state-root height refresh on reconnect
- Prod stabilize: JWT from `.env`, cluster-tip success, failover pre-sync in evidence suite

### Live ops

- `prod_evidence_suite.ps1 -GitTag v1.2.41` **PASS** (stabilize, health, failover, signed tx, EVM)

---

## [1.2.31] — 2026-07-12

### Added

- `--live-prod-mesh` readiness gate for Docker prod mesh :18180–18182
- `scripts/record_evidence_run.py` for local evidence JSON
- Prod mesh health_watch timeouts (reduce soak false FAILs)

---

## [1.2.30] — 2026-07-12

### Changed

- Unified consensus: parallel Casper/Beacon block feeds disabled in prod path
- Genesis ceremony hashes via native crypto kernel
- Industrial gate `--min-soak-hours` for completed soak evidence

### Live ops

- 48h prod mesh soak started; EVM smoke re-PASS on block #7 (all 3 RPC)

---

## [1.2.29] — 2026-07-12

### Added

- Rust RLP kernel (`rlp_encode`, `rlp_decode`, `rlp_decode_single`) for Ethereum raw tx hot path
- `tests/unit/test_rlp_native.py` — native/Python parity

### Changed

- `crypto/rlp.py` uses `abs_native` when available; Python fallback for dev
- Industrial gate + native self-test cover RLP roundtrip

---

## [1.2.28] — 2026-07-12

### Added

- Fail-closed prod `/contract/deploy` (mempool only); CI prod-mesh3 signed-tx + EVM evidence
- Rust `pubkey_to_eth_address`; `KeyGenerator.derive_address_eth()`
- `docs/evidence_run.example.json`; release notes v1.2.28

### Fixed / hardened

- `block_builder` Merkle tx_root aligned with `core.blockchain`
- Cross-shard digests via native `hash_text`
- Industrial gate: abs_native self-test + wheel export checks
- Mining block-sign errors logged; native fail-closed merkle/canonical paths

### Tests

- `test_api_prod_direct_deploy.py`, `test_block_builder_merkle.py`, `test_keygen_native.py`

---

## [1.2.27] — 2026-07-12

### Added

- `RELEASE_NOTES_v1.2.27.md` — verification mermaid flows + copy-paste prod mesh checks

### Fixed

- **Prod mesh mining stall** — `mesh_ready_for_mining` no longer latches on stale P2P wire roots; STATUS height alignment fallback
- **Event loop freeze** — hub P2P broadcast non-blocking; `blockchain.add_block` via `asyncio.to_thread` (EVM deploy no longer blocks mining)
- **Parallel state-root RPC** — faster peer queries; sync engine skips mismatch while peer catching up
- **EVM deploy txs** — `tx_validator` allows zero-value deploy; `prod_evm_smoke.py` mempool-only cross-node path (no direct deploy fallback)
- **Prod JWT** — `verify_p2p_ci._mint_admin_jwt_from_secret()` for mesh when `/auth/token` disabled

### Proven (local Docker mesh)

- Cross-node EVM: mempool deploy + `eth_getStorageAt` on all 3 RPC nodes (Jul 12 evening run)
- See `docs/EVIDENCE_MATRIX.md`

### Tests

- `tests/unit/test_mesh_mining_ready.py` — stale wire + STATUS height fallback cases

---

## [1.2.26] — 2026-07-06

### Added

- `scripts/prod_evm_smoke.py` — prod HTTP deploy + `eth_getStorageAt` on RPC :18546–:18548
- `scripts/prod_evidence_suite.ps1` — one-shot health + failover + signed tx + EVM

### Fixed

- `prod_signed_tx_smoke.py` — missing `import time`

---

## [1.2.25] — 2026-07-06

### Docs

- `docs/EVIDENCE_MATRIX.md` — proven vs not-proven ops (failover, signed tx, EVM prod, soak 24h+, audit)
- README / MAINNET_GAP / PUBLIC_TESTNET aligned with live prod mesh evidence gaps

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
