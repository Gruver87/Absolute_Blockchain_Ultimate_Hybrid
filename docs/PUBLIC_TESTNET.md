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

- [ ] Prod or devnet mesh soak **48h+** (`docker_prod_3node.ps1 -SkipBuild -KeepVolumes`)
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

- [ ] Single seed + 2–3 validators on VPS or cloud (Docker compose or K8s)
- [ ] Prometheus/Grafana or uptime ping on `/health/ready`
- [ ] Log rotation on `data/node.log`
- [ ] Documented restore from `backup_chainstore.ps1`

---

## Go-live (minimal public surface)

1. **Seed node** — HTTP 443 → `:8080`, RPC 443 → `:8545` (or separate host)
2. **Explorer** — static `web/explorer/` behind same host or CDN
3. **README** — replace localhost examples with public URL + chain ID `77777`
4. **Status page** — link to GitHub Actions badges + last release tag

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
