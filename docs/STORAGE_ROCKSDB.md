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

```powershell
.\scripts\backup_chainstore.ps1 -DockerMesh1
# copies checkpoint from running node1 to .\backups\prod-mesh1-<timestamp>
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
- [ ] 24–48 h soak: `docker_prod_3node.ps1` + restart with `-SkipBuild -KeepVolumes`
- [ ] Documented DR restore rehearsal on test volume

### P1 — Hybrid completion

- [ ] Migrate aux tables (NFT, evm_logs, checkpoints, propagation) into Rocks CF or document permanent aux scope
- [ ] Rocks tuning: block cache, write buffers, compaction metrics
- [ ] Benchmark: block commit latency vs SQLite devnet (publish numbers in this doc)

### P2 — Rust storage depth

- [ ] More hot-path encoding in Rust (batch account scan)
- [ ] Tighter `StateRootAccumulator` ↔ `persist_block_atomic` invariant tests on reorg
- [ ] Optional: column families split (blocks / state / index)

### P3 — Not now

- Full Python storage rewrite in Rust
- Sharded Rocks per shard before stable single-chain mainnet
- non-root Docker user + Rocks volumes on Windows (needs separate test)

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
```

---

## Related docs

- [DOCKER_IMAGES.md](DOCKER_IMAGES.md) — prod image build / GHCR
- [MAINNET_GAP_ANALYSIS.md](MAINNET_GAP_ANALYSIS.md) — blockers before public mainnet
- [PORTING_ROADMAP.md](PORTING_ROADMAP.md) — Rust kernel priorities
