# P2P wire TLS (prod mesh default)

TLS on the **P2P port** (default `:5000`) is separate from HTTP/RPC TLS (nginx).

**Prod 3-node mesh:** P2P TLS + mTLS is the **default** (`.\scripts\docker_prod_3node.ps1`). Use `-NoP2pTls` only for local plaintext labs.

## Threat model (honest)

- TLS encrypts the P2P wire (TLS 1.2+).
- When TLS is enabled, **both** server and client use `CERT_REQUIRED` (no `CERT_NONE` path).
- mTLS authenticates peer certificates against the mesh CA (`P2P_TLS_CA_PATH`).
- Handshake `node_id` is **bound** to peer cert CN/SAN (`P2P_TLS_BIND_IDENTITY=true` by default). Cert CN must equal config `node_id` (prod mesh: `docker-prod-mesh-1` …).
- Optional SHA-256 DER fingerprint allowlist: `P2P_TLS_PEER_FINGERPRINTS` (comma-separated).
- Still not a full libp2p identity stack — rotation / SPIFFE / hardware-backed keys are out of scope until post-audit.

## Config / env

| Variable | Default | Description |
|----------|---------|-------------|
| `P2P_TLS_ENABLED` | `false` (dev) / **true** on prod mesh JSON | Wrap P2P TCP with TLS 1.2+ |
| `P2P_TLS_CERT_PATH` | — | Node certificate (PEM) |
| `P2P_TLS_KEY_PATH` | — | Node private key (PEM) |
| `P2P_TLS_CA_PATH` | — | CA bundle to verify peers (**required** when TLS on) |
| `P2P_TLS_REQUIRE_CLIENT_CERT` | **true** on prod mesh | Documented mTLS intent (verify mode is always CERT_REQUIRED when TLS on) |
| `P2P_TLS_FAIL_CLOSED` | `true` | Reject insecure TLS verify modes |
| `P2P_TLS_BIND_IDENTITY` | `true` | Require handshake `node_id` ∈ peer cert CN/SAN |
| `P2P_TLS_PEER_FINGERPRINTS` | empty | Optional allowlist of peer cert SHA-256 hex digests |

All peers in a mesh must use the same CA; each node cert CN must match that node's `node_id`.

## Dev self-signed material

```bash
python scripts/gen_p2p_dev_tls.py --out-dir data/p2p_tls_dev --node-id dev-node-1
```

**Windows:** `gen_p2p_mesh_tls.py` uses OpenSSL from PATH if present (e.g. Git for Windows), otherwise falls back to the `cryptography` Python package (already in `requirements.txt`).

## Docker prod 3-node mesh

```powershell
python scripts/gen_p2p_mesh_tls.py   # CN = docker-prod-mesh-1..3 (matches mesh JSON node_id)
.\scripts\docker_prod_3node.ps1      # TLS+mTLS overlay ON by default
# plaintext lab only:
.\scripts\docker_prod_3node.ps1 -NoP2pTls
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

Prod mesh TLS is the default path. For a dedicated TLS soak:

```powershell
.\scripts\prepare_48h_soak.ps1 -RequireP2pTls
```

Use `-NoP2pTls` on `docker_prod_3node.ps1` only for plaintext lab meshes.

## Observability

- `GET /p2p/security` → `tls` block (`enabled`, `ready`, `fail_closed`, `identity_binding`, `fingerprint_allowlist`, `errors`)
- Industrial gate warns when `deployment_mode=prod` and `p2p_tls_enabled=false`

## HTTP vs P2P

- **HTTP/RPC**: terminate TLS at nginx — see [TLS_NGINX.md](TLS_NGINX.md)
- **P2P gossip/sync**: enable `P2P_TLS_*` on the node config (this document)
