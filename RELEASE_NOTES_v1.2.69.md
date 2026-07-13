# Release Notes — v1.2.69

## Public testnet VPS toolkit

### Local evidence path (full)

```powershell
.\scripts\testnet_evidence_suite.ps1
# optional 2-node:
.\scripts\testnet_evidence_suite.ps1 -WithValidator
```

### Uptime monitoring (VPS cron)

```powershell
.\scripts\testnet_uptime_probe.ps1 -Append
```

Files: `logs/testnet_uptime.json`, `logs/testnet_uptime.jsonl`

### nginx on VPS

```bash
sudo bash deploy/nginx/install_testnet_nginx.sh testnet.yourdomain.com
sudo certbot --nginx -d testnet.yourdomain.com
```

### Monolith gate

```powershell
.\scripts\monolith_gate.ps1 -VpsTestnetPreflight
.\scripts\monolith_gate.ps1 -VpsTestnetPreflight -VpsTestnetLive   # after seed on :19080
```

### Validator ports

Second validator now defaults to `:19081` HTTP (not `:9081` — avoids Windows conflicts).

## Verify

```powershell
pytest tests/unit/test_testnet_uptime_probe.py tests/unit/test_public_testnet_gate.py -q
python scripts/public_testnet_gate.py
```
