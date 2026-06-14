# Changelog

Все значимые изменения документируются здесь. Формат основан на [Keep a Changelog](https://keepachangelog.com/).

**Текущая волна API:** `api_wave = 55` (проверка: `GET /status`)

---

## [1.2.0-industrial] — Wave 37–55 (июнь 2026)

### Wave 55 — 5-validator devnet

- `docker-compose.devnet-5validator.yml` — 5 nodes `:8080`–`:8084`, 3 miners + 2 attesters
- `docker/validators.devnet5.json` — manifest; addresses derived at runtime (no keys on disk)
- `GET /testnet/validators` — validator set health, proposer rotation stats
- Mining proposer gate — only selected validator forges when `active_validators > 1`
- `verify_p2p_ci.py --mode devnet5`; `.\scripts\docker_devnet_5validator.ps1`

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
- MEV simulator: история в SQLite, `GET /mev/history`

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
- Bridge / Lightning / Plasma / MEV — **demo / simulator** с реальными L1-эффектами где указано
- Крипто-аудит не проводился

См. [DISCLAIMER.md](DISCLAIMER.md) и **Часть 0** в [docs/ALL_COMMANDS.txt](docs/ALL_COMMANDS.txt).
