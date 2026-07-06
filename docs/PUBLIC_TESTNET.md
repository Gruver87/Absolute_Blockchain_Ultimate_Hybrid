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

- [ ] Prod or devnet mesh soak **48h+** (`.\scripts\soak_monitor.ps1 -ProdMesh -Hours 48`)
- [x] Automated local gate: `.\scripts\testnet_readiness.ps1 -ProdMesh`
- [ ] `probe_mesh_nodes.ps1` green on all HTTP/RPC/P2P ports
- [ ] `GET /chain/consistency/harness` aligned on all validators
- [ ] DR rehearsal passed (`dr_restore_rehearsal.ps1 -DockerMesh1`)

### Security

- [ ] TLS (Let's Encrypt or cloud LB)
- [ ] Rate limits (`RATE_LIMIT_RPM`) on public REST/RPC
- [ ] RPC API keys required on admin/write paths
- [ ] CORS restricted to explorer origin
- [ ] No `.env` secrets in repo; rotate JWT / bridge oracle keys
- [ ] CI green: tests + docker + `security-audit.yml`

### Ops

- [x] Docker seed compose: `docker-compose.testnet.yml` + `scripts/docker_testnet_seed.ps1`
- [x] nginx TLS template: `deploy/nginx/testnet.example.conf`
- [ ] Single seed + 2–3 validators on VPS or cloud (Docker compose or K8s)
- [ ] Prometheus/Grafana or uptime ping on `/health/ready`
- [ ] Log rotation on `data/node.log`
- [ ] Documented restore from `backup_chainstore.ps1`

---

## Go-live (minimal public surface)

1. **Local / VPS seed** — `.\scripts\docker_testnet_seed.ps1` (ports `9080` HTTP, `9085` RPC by default)
2. **TLS** — `deploy/nginx/testnet.example.conf` in front of seed ports
3. **Explorer** — static `web/explorer/` behind same host or CDN
4. **README** — replace localhost examples with public URL + chain ID `77777`
5. **Status page** — link to GitHub Actions badges + last release tag
6. **Gate** — `.\scripts\testnet_readiness.ps1 -Ports 9080`

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

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [DOCKER_IMAGES.md](DOCKER_IMAGES.md)
- [COMMANDS_REFERENCE.md](COMMANDS_REFERENCE.md)
