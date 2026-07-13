# VPS deployment for public testnet seed (chain 77777). Honest scope: infra is operator-owned.

**Target:** single Linux VPS (Ubuntu 22.04+), Docker, nginx + TLS.

Local proof already done: `testnet_evidence_suite.ps1` on `:19080`.

---

## 1. Provision VPS

- 2 vCPU, 4 GB RAM minimum
- Open ports: **443** (nginx), **19080** HTTP (optional direct), **19085** RPC (restrict by firewall to your IP if not behind nginx)
- SSH key auth only

---

## 2. Bootstrap on server

```bash
git clone https://github.com/Gruver87/Absolute_Blockchain_Ultimate_Hybrid.git
cd Absolute_Blockchain_Ultimate_Hybrid
cp .env.testnet.example .env.testnet
# edit .env.testnet: JWT_SECRET, RPC_API_KEYS, CORS_ORIGINS=https://your-domain
bash scripts/vps_testnet_bootstrap.sh
python3 scripts/public_testnet_gate.py --live --base-url http://127.0.0.1:19080
```

---

## 3. TLS (nginx)

```bash
sudo apt install nginx certbot python3-certbot-nginx
sudo bash deploy/nginx/install_testnet_nginx.sh testnet.yourdomain.com
sudo certbot --nginx -d testnet.yourdomain.com
sudo nginx -t && sudo systemctl reload nginx
```

Explorer static files: copy `web/explorer/` to `/var/www/abs-explorer`.

## 4. Uptime monitoring

```bash
# cron every 5 minutes on VPS
*/5 * * * * cd /opt/Absolute_Blockchain_Ultimate_Hybrid && python3 scripts/testnet_uptime_probe.py --append
```

Snapshot: `logs/testnet_uptime.json` · history: `logs/testnet_uptime.jsonl`

---

## 5. Verify

```bash
curl -s https://testnet.yourdomain.com/api/health/ready
python3 scripts/public_testnet_gate.py --live --base-url https://testnet.yourdomain.com/api
```

From your workstation (after DNS):

```powershell
.\scripts\public_testnet_gate.ps1 -Live -BaseUrl https://testnet.yourdomain.com/api
```

---

## 5. Ops

- Daily: block height + peer count
- Weekly: `backup_chainstore.ps1` equivalent on VPS data volume
- Upgrades: `docker compose -f docker-compose.testnet.yml pull && up -d`

---

## Not included (honest)

- Mainnet prod mesh (778888) on public VPS without separate hardening review
- DDoS protection beyond nginx rate limits
- 48h soak on VPS (run after deploy; separate from local prod mesh soak)

See [PUBLIC_TESTNET.md](PUBLIC_TESTNET.md), [MAINNET_CUTOVER.md](MAINNET_CUTOVER.md).
