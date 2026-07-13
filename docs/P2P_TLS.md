# P2P wire TLS (optional)

TLS on the **P2P port** (default `:5000`) is separate from HTTP/RPC TLS (nginx). Enable for public mainnet or VPS mesh where the P2P port is exposed.

## Config / env

| Variable | Default | Description |
|----------|---------|-------------|
| `P2P_TLS_ENABLED` | `false` | Wrap P2P TCP with TLS 1.2+ |
| `P2P_TLS_CERT_PATH` | — | Node certificate (PEM) |
| `P2P_TLS_KEY_PATH` | — | Node private key (PEM) |
| `P2P_TLS_CA_PATH` | — | CA bundle to verify peers |
| `P2P_TLS_REQUIRE_CLIENT_CERT` | `false` | mTLS: require client cert |

All peers in a mesh must use the same CA and compatible certs.

## Dev self-signed material

```bash
python scripts/gen_p2p_dev_tls.py --out-dir data/p2p_tls_dev --node-id dev-node-1
```

**Windows:** `gen_p2p_mesh_tls.py` uses OpenSSL from PATH if present (e.g. Git for Windows), otherwise falls back to the `cryptography` Python package (already in `requirements.txt`).

Copy the printed env vars into `.env` or node config for each node (unique CN per node, same `P2P_TLS_CA_PATH`).

## Docker prod 3-node mesh

Generate mesh certs and start with P2P TLS overlay:

```powershell
python scripts/gen_p2p_mesh_tls.py
.\scripts\docker_prod_3node_p2ptls.ps1
# or
.\scripts\docker_prod_3node.ps1 -P2pTls
```

Uses `docker-compose.prod.3node.p2ptls.yml` (mounts `data/p2p_tls_prod_mesh/nodeN` → `/app/p2p_tls`).

### Verify and evidence

```powershell
.\scripts\probe_p2p_tls_mesh.ps1
python scripts/verify_p2p_tls_mesh.py --wait 120
.\scripts\p2p_tls_evidence_suite.ps1
.\scripts\prod_mesh_resilience_suite.ps1 -P2pTls -SkipDrRehearsal
```

Report: `logs/p2p_tls_mesh_verify.json`

Preflight (static or live):

```powershell
.\scripts\prepare_p2p_tls_mesh.ps1
.\scripts\prepare_p2p_tls_mesh.ps1 -Live -WaitSec 60
.\scripts\monolith_gate.ps1 -P2pTlsPreflight
.\scripts\monolith_gate.ps1 -P2pTlsPreflight -P2pTlsLive
```

### 48h soak with TLS

When mesh runs with `-P2pTls`:

```powershell
.\scripts\prepare_48h_soak.ps1 -RequireP2pTls
```

Default off (plain TCP) when `-P2pTls` is omitted — matches existing local prod mesh workflows.

## Observability

- `GET /p2p/security` → `tls` block (`enabled`, `ready`, `errors`)
- Industrial gate warns when `deployment_mode=prod` and `p2p_tls_enabled=false`

## HTTP vs P2P

- **HTTP/RPC**: terminate TLS at nginx — see [TLS_NGINX.md](TLS_NGINX.md)
- **P2P gossip/sync**: enable `P2P_TLS_*` on the node config (this document)
