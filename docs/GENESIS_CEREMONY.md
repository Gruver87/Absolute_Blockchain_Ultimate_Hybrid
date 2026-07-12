# Genesis Ceremony — Mainnet Launch

**Purpose:** Publish an immutable validator set + tokenomics snapshot before public mainnet.

Automated builder: `runtime/genesis_ceremony.py` / `scripts/genesis_ceremony.py`

---

## Prerequisites

- [x] Mainnet v1 `chain_id` **778888** (`runtime/mainnet_constants.py` — `MAINNET_V1_CHAIN_ID`)
- [ ] Real validator **private keys** generated offline (`scripts/genesis_ceremony_keygen.py`)
- [ ] Each node's `data/wallet.json` verified against manifest (`scripts/genesis_ceremony_verify_wallet.py`)
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

Strict check (reject zero-prefix and repetitive template addresses):

```powershell
python scripts/genesis_ceremony.py --strict-mainnet `
  --config node.prod.mainnet-v1.example.json `
  --manifest validators.manifest.mainnet-v1.example.json
python scripts/genesis_ceremony_addresses.py
```

### 2b. Generate operator keys (offline ceremony)

Replace template addresses with freshly generated ECDSA keys (never commit output):

```powershell
python scripts/genesis_ceremony_keygen.py --out-dir data/ceremony_keys
python scripts/genesis_ceremony_keygen.py --out-dir data/ceremony_keys --verify
python scripts/mainnet_launch_checklist.py --ceremony-dir data/ceremony_keys
```

Deploy `data/ceremony_keys/validators.manifest.json` as prod `validators_manifest_path`.
Copy `wallets/validator-N.wallet.json` to each validator node's `data/wallet.json`.

Verify binding:

```powershell
python scripts/genesis_ceremony_verify_wallet.py `
  --wallet data/ceremony_keys/wallets/validator-1.wallet.json `
  --manifest data/ceremony_keys/validators.manifest.json `
  --index 1
```

Before public cutover:

```powershell
python scripts/mainnet_launch_checklist.py --strict-mainnet --strict-keys --ceremony-dir data/ceremony_keys
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
python scripts/ceremony_preflight.py --ceremony-dir data/ceremony_keys --require-env-pin
python scripts/mainnet_launch_checklist.py
python scripts/mainnet_launch_checklist.py --strict-mainnet --ceremony-dir data/ceremony_keys
.\scripts\mainnet_live_gate.ps1 -CeremonyDir data/ceremony_keys
.\scripts\docker_prod.ps1 -CeremonyDir data/ceremony_keys
```

Secret rotation (JWT / RPC / bridge oracle) is separate from ceremony — see [SECRET_ROTATION.md](SECRET_ROTATION.md).

---

## After ceremony

- Archive `data/genesis_ceremony.json` in secure storage
- Update explorer / docs with `chain_id` and `ceremony_hash`
- Mark audit item when vendor report received:

```powershell
python scripts/external_audit_tracker.py --set "Third-party smart-contract / L1 security audit completed" --note "Vendor YYYY-MM-DD report ID"
```
