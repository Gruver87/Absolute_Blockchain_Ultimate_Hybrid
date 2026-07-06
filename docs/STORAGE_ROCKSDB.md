# RocksDB storage architecture (honest)

**Updated:** 2026-07-05  
**Scope:** prod mainnet-v1 prep (chain 778888) — not a launched public mainnet

---

## Two engines in one repo

| Profile | `db_engine` | Hot path | Used by |
|---------|-------------|----------|---------|
| Dev / local default | `sqlite` | `data/blockchain.db` | `python main.py`, devnet Docker 77777 |
| Prod / mainnet prep | **`rocksdb`** | `data/chainstore/` | prod mesh, `node.prod*.json`, prod gate |

`prod_gate.py` **requires** `db_engine=rocksdb` on all prod profiles.

---

## Hybrid layout (prod)

```
data/                          # or Docker volume /app/data
├── chainstore/                # RocksDB LSM (blocks, accounts, txs, bridge, …)
│   ├── aux.db                 # SQLite sidecar (NFT, EVM logs, legacy tables)
│   └── …rocksdb files…
├── wallet.json
└── validators.manifest.json
```

**`HybridDatabase`** (`storage/hybrid_database.py`):

- **Rocks core** — L1 hot path via `RocksChainStore` + native `RocksEngine` (PyO3)
- **SQLite aux** — cold / dev-only tables; unknown methods delegate via `__getattr__` → `_aux`

Bridge locks/credits live in **Rocks**, not aux (since P1 migration).

---

## Rust involvement (truthful)

| Component | Language | Notes |
|-----------|----------|-------|
| `RocksEngine` | Rust PyO3 | get/put/write_batch/checkpoint/iter |
| `RocksChainStore` | Python | key encoding, business logic, atomic block commit |
| `StateRootAccumulator` | Rust | incremental state root during commits |
| Crypto / EVM kernels | Rust | `abs_native` — prod required |
| P2P / REST / consensus policy | Python | intentional |

**Not true yet:** “full Rust node” or “100% Rocks without aux.db”.

---

## Prod mesh seeding

1. node1 starts alone (height ≤ 1 before seed)
2. node1 stopped → `node2-db-seed` / `node3-db-seed` copy `chainstore/` (Rocks checkpoint or directory copy)
3. all three start together → P2P mesh on `:18180–18182`

Script: `scripts/docker_prod_3node.ps1`  
Clone helper: `storage/chain_clone.py`

---

## Backup & restore

### Local / bind-mounted data

```powershell
# Backup
python scripts/backup_chainstore.py --data-dir data --dest backups/my-snapshot

# Restore (destructive on target)
python scripts/restore_chainstore.py --backup-dir backups/my-snapshot --data-dir data --force --verify
```

### Prod Docker mesh node1

Uses a stdin-piped inline script (`docker_backup_in_container.py`) so backup works **without rebuilding** the prod image after v1.2.3.

Default: **brief node1 stop** + `docker run` on the **existing node1 image** (no `compose run` / rebuild). Optional `-Live` tries read-only open while node1 runs.

```powershell
.\scripts\backup_chainstore.ps1 -DockerMesh1
.\scripts\dr_restore_rehearsal.ps1 -DockerMesh1
# copies checkpoint from node1 to .\backups\prod-mesh1-<timestamp>
```

Core logic: `storage/chain_backup.py` (Rocks `checkpoint` via `RocksEngine.checkpoint`).

### CI drills

| Script | Engine |
|--------|--------|
| `scripts/backup_db_drill.py` | SQLite (legacy) |
| `scripts/backup_rocks_drill.py` | RocksDB (skipped if no native wheel) |

---

## Migration SQLite → Rocks

One-time for legacy nodes:

```powershell
python scripts/migrate_sqlite_to_rocks.py --source data/blockchain.db --dest data/chainstore --verify
```

Then set `DB_ENGINE=rocksdb` / `"db_engine": "rocksdb"` in config.

---

## Roadmap (engineering order)

### P0 — Stability (now)

- [x] Prod mesh on RocksDB
- [x] Backup/restore scripts + CI rocks drill
- [ ] 24–48 h soak: `.\scripts\soak_monitor.ps1 -ProdMesh -Hours 24`
- [x] Documented DR restore rehearsal on test volume (`scripts/dr_restore_rehearsal.ps1`)
- [x] `health_watch.ps1` quick/full harness polls + mesh height alignment

### P1 — Hybrid completion

- [x] Document permanent aux scope (see below)
- [x] Rocks tuning env vars + LSM property introspection in `get_stats()`
- [x] Benchmark script `scripts/bench_storage_commit.py` (run locally; numbers vary by disk)
- [ ] Migrate optional aux tables into Rocks CF (NFT, evm_logs, …)

### P2 — Rust storage depth

- [ ] More hot-path encoding in Rust (batch account scan)
- [ ] Tighter `StateRootAccumulator` ↔ `persist_block_atomic` invariant tests on reorg
- [ ] Optional: column families split (blocks / state / index)

### P3 — Not now

- Full Python storage rewrite in Rust
- Sharded Rocks per shard before stable single-chain mainnet
- non-root Docker user + Rocks volumes on Windows (needs separate test)

---

## Aux.db scope (honest, v1.2.4)

**In Rocks (hot path):** blocks, accounts, transactions, validators, meta, bridge locks/credits, receipts, proposer audit, state-root mismatch log.

**Stays in SQLite aux (cold / dev modules):** NFT, EVM logs, lightning/plasma, wasm/ai agents, oracle feeds, mev/reorg diagnostics, tx propagation events, legacy minivm tables. These are accessed via `HybridDatabase.__getattr__` → `_aux` and are **not required** for prod mainnet-v1 consensus or bridge L1 cutover.

Migration of aux rows into Rocks CF is **optional P1+** — not a mainnet blocker while prod gate keeps `db_engine=rocksdb` on the Rocks core.

---

## Rocks tuning (prod)

| Env / config | Default | Notes |
|--------------|---------|-------|
| `ROCKSDB_SYNC` | `FULL` | Durable WAL on prod |
| `ROCKSDB_BLOCK_CACHE_MB` | `256` | LRU block cache; `0` = Rocks default |
| `ROCKSDB_WRITE_BUFFER_MB` | `64` | Memtable size; `0` = Rocks default |

`GET /stats` (via `db.get_stats()`) includes `rocksdb_tuning` and live `rocksdb_properties` (memtable size, SST bytes, compactions) when native wheel supports it.

---

## Commands cheat sheet

```powershell
# Verify native + Rocks
python -c "import abs_native; print('RocksEngine', hasattr(abs_native,'RocksEngine'))"

# Prod mesh
.\scripts\docker_prod_3node.ps1
.\scripts\probe_mesh_nodes.ps1 -ProdMesh

# Tests
pytest tests/unit/test_rocks_store.py tests/unit/test_rocks_blockchain_integration.py -q

# DR
python scripts/backup_rocks_drill.py
python scripts/bench_storage_commit.py --blocks 20

# DR rehearsal (PowerShell, ASCII-safe)
.\scripts\dr_restore_rehearsal.ps1 -DataDir data
```

---

## Related docs

- [DOCKER_IMAGES.md](DOCKER_IMAGES.md) — prod image build / GHCR
- [MAINNET_GAP_ANALYSIS.md](MAINNET_GAP_ANALYSIS.md) — blockers before public mainnet
- [PORTING_ROADMAP.md](PORTING_ROADMAP.md) — Rust kernel priorities
