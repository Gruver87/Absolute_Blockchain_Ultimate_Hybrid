# Public testnet checklist (not live yet)

**Status:** planning doc — no public URL is promised until every item in **Go-live** is checked.

Target (example): `https://testnet.absolute-chain.org` → explorer + RPC behind TLS.

---

## What it would be

| Field | Value |
|-------|-------|
| Network | **Devnet** chain ID `77777` (not mainnet-v1 `778888`) |
| Purpose | Public R&D demo, explorer, P2P seed — **not** real funds |
| Disclaimer | Same as README: not audited mainnet, ABS not tradable |

---

## Prerequisites (before DNS)

### Stability

- [ ] Prod mesh soak **48h+ completed** (`soak_report.json` passed) — see [EVIDENCE_MATRIX.md](EVIDENCE_MATRIX.md)
- [x] Automated local gate: `.\scripts\testnet_readiness.ps1 -ProdMesh`
- [x] Soak restart with v1.2.31+ timeouts: `.\scripts\restart_soak_prod_mesh.ps1 -Hours 48`
- [x] Failover drill on prod mesh (`prod_mesh_failover.ps1`) with recorded heights
- [ ] `probe_mesh_nodes.ps1` green on all HTTP/RPC/P2P ports
- [x] Testnet mesh verify: `.\scripts\docker_testnet_mesh.ps1` / `probe_testnet_mesh.ps1 -Deep`
- [ ] `GET /chain/consistency/harness` aligned on all validators
- [ ] DR rehearsal passed (`dr_restore_rehearsal.ps1 -DockerMesh1`)

### Security

- [ ] TLS (Let's Encrypt or cloud LB)
- [ ] Rate limits (`RATE_LIMIT_RPM`) on public REST/RPC
- [ ] RPC API keys required on admin/write paths
- [ ] CORS restricted to explorer origin
- [ ] No `.env` secrets in repo; rotate JWT / bridge oracle keys
- [ ] CI green: tests + docker + `security-audit.yml`

**Windows note:** port **9080** is often taken by NahimicService (MSI audio). Default testnet HTTP port is **19080** (see `.env.testnet.example`).

### Ops

- [x] Docker seed compose: `docker-compose.testnet.yml` + `scripts/docker_testnet_seed.ps1`
- [x] nginx TLS template: `deploy/nginx/testnet.example.conf`
- [x] Static + live gate: `scripts/public_testnet_gate.py` / `.ps1`
- [x] Linux VPS bootstrap: `scripts/vps_testnet_bootstrap.sh`
- [x] VPS preflight: `scripts/vps_testnet_preflight.py` / `prepare_vps_testnet.ps1`
- [x] Uptime probe (cron): `scripts/testnet_uptime_probe.py` → `logs/testnet_uptime.json`
- [x] nginx install helper: `deploy/nginx/install_testnet_nginx.sh`
- [x] Evidence suite: `.\scripts\testnet_evidence_suite.ps1` (seed + gates + VPS preflight)
- [ ] Single seed + 2–3 validators on VPS or cloud (Docker compose or K8s)
- [ ] Prometheus/Grafana or uptime ping on `/health/ready`
- [ ] Log rotation on `data/node.log`
- [ ] Documented restore from `backup_chainstore.ps1`

---

## Go-live (minimal public surface)

1. **Local / VPS seed** — `.\scripts\docker_testnet_seed.ps1` (default HTTP **19080** — avoids Windows Nahimic on :9080)
2. **Gate** — `python scripts/public_testnet_gate.py --live` (add `--require-soak-hours 48` before DNS)
3. **VPS preflight** — `.\scripts\prepare_vps_testnet.ps1` (static) or `-Live` after local seed
4. **TLS** — `deploy/nginx/testnet.example.conf` in front of seed ports
5. **Explorer** — static `web/explorer/` behind same host or CDN
6. **README** — replace localhost examples with public URL + chain ID `77777`
7. **Status page** — link to GitHub Actions badges + last release tag
8. **Gate** — `.\scripts\testnet_readiness.ps1 -TestnetSeed -MinSoakHours 0` or `.\scripts\testnet_evidence_suite.ps1`

Example nginx pattern (illustrative):

```
https://testnet.example.com/          -> explorer
https://testnet.example.com/api/      -> node :8080
https://testnet.example.com/rpc/      -> node :8545 (key required)
```

---

## Honest messaging (copy-paste safe)

> Public **devnet** node for Absolute Blockchain Ultimate Hybrid. Chain ID **77777**. Not mainnet. Not audited for production funds. API may reset during upgrades.

---

## After launch

- [ ] Monitor peer count and block height drift daily
- [ ] Weekly backup + quarterly DR rehearsal
- [ ] Issue tracker label `testnet` for public reports

---

## Related

- [VPS_DEPLOY.md](VPS_DEPLOY.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [DOCKER_IMAGES.md](DOCKER_IMAGES.md)
- [COMMANDS_REFERENCE.md](COMMANDS_REFERENCE.md)
