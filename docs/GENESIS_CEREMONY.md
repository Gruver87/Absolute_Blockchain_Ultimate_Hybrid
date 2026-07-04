# Genesis Ceremony — Mainnet Launch

**Purpose:** Publish an immutable validator set + tokenomics snapshot before public mainnet.

Automated builder: `runtime/genesis_ceremony.py` / `scripts/genesis_ceremony.py`

---

## Prerequisites

- [ ] Final `chain_id` chosen (replace placeholder `778888` in prod configs)
- [ ] Real validator `0x` addresses in manifest (no `0x000…0001` placeholders)
- [ ] Founder address decided (optional override)
- [ ] All nodes use **deterministic genesis** (`resolve_genesis_timestamp()` from `chain_id`)
- [ ] Third-party security audit complete (organizational gate)

---

## Steps

### 1. Prepare validator manifest

Edit `validators.manifest.mainnet-v1.example.json` (template) or your production file (e.g. `validators.mainnet.json`):

- Public addresses only — **no private keys**
- `mines`, `stake`, `shard_id` per operator agreement
- Point prod `validators_manifest_path` to this file

### 2. Build ceremony artifact

```powershell
python scripts/genesis_ceremony.py `
  --config node.prod.mainnet-v1.example.json `
  --manifest validators.mainnet.json `
  --write data/genesis_ceremony.json
```

Strict check (reject placeholder addresses):

```powershell
python scripts/genesis_ceremony.py --strict-mainnet `
  --config node.prod.mainnet-v1.example.json `
  --manifest validators.mainnet.json
```

### 3. Publish hashes

Record and publish out-of-band:

| Field | Description |
|-------|-------------|
| `chain_id` | Network ID |
| `validator_set_hash` | Hash of canonical validator set |
| `genesis_alloc_hash` | Genesis balance allocation |
| `ceremony_hash` | Combined ceremony fingerprint |

Pin the ceremony at deploy time so nodes refuse a mismatched manifest:

```powershell
$env:GENESIS_CEREMONY_HASH = "<ceremony_hash from step 2>"
# Docker prod:
$env:GENESIS_STRICT_MAINNET = "true"   # after real validator addresses are in manifest
```

`docker-compose.prod.yml` forwards `GENESIS_CEREMONY_HASH` and `GENESIS_STRICT_MAINNET` into the node container. `/status` exposes `genesis_ceremony.ready`, `ceremony_hash`, and `mainnet_addresses_ready`.

### 4. Genesis block verification

All nodes must produce **identical genesis hash** for the same `chain_id`:

```powershell
python -m pytest tests/unit/test_genesis_deterministic.py -q
```

Fresh DB if upgrading from old non-deterministic genesis:

```powershell
.\scripts\start_two_nodes.ps1 -Fresh
```

### 5. Coordinated launch

1. Stop all nodes
2. Deploy matching config + manifest + secrets via env
3. Start validators simultaneously
4. Verify mesh: `python scripts/verify_p2p_ci.py --mode prod-smoke`

---

## Full launch checklist

```powershell
python scripts/mainnet_launch_checklist.py
python scripts/mainnet_launch_checklist.py --strict-mainnet   # before public cutover
python scripts/mainnet_readiness.py --no-strict-audit --json
```

---

## After ceremony

- Archive `data/genesis_ceremony.json` in secure storage
- Update explorer / docs with `chain_id` and `ceremony_hash`
- Mark audit item when vendor report received:

```powershell
python scripts/external_audit_tracker.py --set "Third-party smart-contract / L1 security audit completed" --note "Vendor YYYY-MM-DD report ID"
```
