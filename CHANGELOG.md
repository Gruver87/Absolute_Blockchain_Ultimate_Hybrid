# Changelog

Все значимые изменения документируются здесь. Формат основан на [Keep a Changelog](https://keepachangelog.com/).

**Текущая волна API:** `api_wave = 50` (проверка: `GET /status`)

---

## [1.2.0-industrial] — Wave 37–50 (июнь 2026)

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
| `pytest tests/unit` | 210 passed, 1 skipped |
| Docker devnet 2 nodes | P2P sync, heights aligned, `state_roots_match=True` |
| `api_wave` | 50 |
| `mega_audit.py` | 256 REST routes |

---

## Честно: что это **не** даёт

- Не production mainnet
- Не полный EVM / не Ethereum-совместимость на 100%
- Bridge / Lightning / Plasma / MEV — **demo / simulator** с реальными L1-эффектами где указано
- Крипто-аудит не проводился

См. [DISCLAIMER.md](DISCLAIMER.md) и **Часть 0** в [docs/ALL_COMMANDS.txt](docs/ALL_COMMANDS.txt).
