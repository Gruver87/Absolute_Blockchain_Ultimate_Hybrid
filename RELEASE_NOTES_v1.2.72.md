# Release Notes — v1.2.72

## VPS 3-node mesh bootstrap

On Linux VPS after cloning the repo:

```bash
cp .env.testnet.example .env.testnet   # rotate secrets
bash scripts/vps_testnet_bootstrap_mesh3.sh
python3 scripts/verify_testnet_mesh.py --mesh3 --wait 120
```

## DNS + TLS cutover probe

After nginx + certbot on the VPS:

```powershell
.\scripts\prepare_testnet_dns_cutover.ps1 -Domain testnet.yourdomain.com
```

```bash
python3 scripts/testnet_dns_cutover.py --domain testnet.yourdomain.com
```

Report: `logs/testnet_dns_cutover.json`

Checks: DNS A/AAAA, TLS handshake, `https://<domain>/api/health/ready`, chain `77777`.

## VPS preflight (mesh3)

```powershell
.\scripts\prepare_vps_testnet.ps1 -Live -Mesh3
.\scripts\prepare_vps_testnet.ps1 -Domain testnet.yourdomain.com
```

## nginx

Template now includes port **80** with `/.well-known/acme-challenge/` for certbot.

## Verify

```powershell
pytest tests/unit/test_testnet_dns_cutover.py tests/unit/test_vps_testnet_preflight.py -q
```
