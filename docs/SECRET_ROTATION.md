# Secret rotation — production operators

**Purpose:** rotate JWT, RPC, and bridge oracle secrets without changing genesis ceremony pin or chain identity.

Ceremony hash and validator manifest must **not** change during secret rotation unless you run a new genesis ceremony.

---

## When to rotate

- Before public mainnet cutover (replace dev/bootstrap secrets)
- After suspected leak of `.env`, wallet backup, or RPC key
- Quarterly operational policy (recommended for prod operators)

---

## What rotates

| Secret | Env var | Impact |
|--------|---------|--------|
| Admin JWT signing | `JWT_SECRET` | All admin API tokens invalid; re-login |
| JSON-RPC API keys | `RPC_API_KEYS` | Update wallets/explorer RPC clients |
| Bridge oracle HMAC | `BRIDGE_ORACLE_SECRET` | Bridge oracle callbacks must use new secret |

## What is preserved

- `GENESIS_CEREMONY_HASH`
- `VALIDATORS_MANIFEST_PATH`
- `CHAIN_ID` (778888)
- `ETH_RPC_URL`, `CORS_ORIGINS`, bridge flags

---

## Procedure

### 1. Backup

```powershell
Copy-Item .env .env.backup.manual
```

### 2. Rotate (dry-run then apply)

```powershell
.\scripts\rotate_prod_secrets.ps1          # preview
.\scripts\rotate_prod_secrets.ps1 -Force   # apply + timestamped .env.bak.*
```

### 3. Restart prod mesh

```powershell
docker compose -f docker-compose.prod.3node.yml down
.\scripts\docker_prod_3node.ps1 -SkipBuild -KeepVolumes
```

### 4. Verify

```powershell
python scripts/mainnet_readiness.py --live-prod-mesh --no-strict-audit
python scripts/ceremony_preflight.py --ceremony-dir data/ceremony_keys --require-env-pin
```

---

## Ceremony pin (separate from rotation)

Secret rotation does **not** replace genesis ceremony setup:

```powershell
python scripts/genesis_ceremony_keygen.py --out-dir data/ceremony_keys
python scripts/ceremony_preflight.py --ceremony-dir data/ceremony_keys --strict-mainnet
.\scripts\pin_ceremony_hash.ps1 -CeremonyDir data\ceremony_keys -StrictMainnet
.\scripts\docker_prod_3node.ps1 -CeremonyDir data\ceremony_keys
```

See [GENESIS_CEREMONY.md](GENESIS_CEREMONY.md).

---

## Honest scope

Rotating `.env` locally proves the **automation works** — production cutover still requires coordinated validator ops and recorded evidence in `data/evidence_run.json`.
