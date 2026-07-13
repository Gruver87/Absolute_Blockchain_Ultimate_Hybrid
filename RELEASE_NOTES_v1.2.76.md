# Release Notes — v1.2.76

## Fixes (Windows P2P TLS path)

1. **PowerShell parse error** in `docker_prod_3node.ps1` when using `-P2pTls` (em-dash in error string).
2. **`gen_p2p_mesh_tls.py`** no longer requires `openssl` in PATH:
   - tries Git for Windows `openssl.exe`
   - falls back to Python `cryptography` package

## Correct order on Windows

```powershell
# 1. Fix prod .env (if node crash-loops on RPC_API_KEYS):
.\scripts\rotate_prod_secrets.ps1 -Force
docker compose -p abs-prod-mesh3 -f docker-compose.prod.3node.yml up -d --force-recreate node1 node2 node3

# 2. Generate TLS material (no openssl needed if cryptography installed):
python scripts/gen_p2p_mesh_tls.py

# 3. Start mesh with P2P TLS:
.\scripts\docker_prod_3node_p2ptls.ps1 -CeremonyDir data/ceremony_keys -SkipBuild

# 4. Verify:
.\scripts\probe_p2p_tls_mesh.ps1 -WaitSec 120
```

## Verify

```powershell
pytest tests/unit/test_gen_p2p_mesh_tls.py tests/unit/test_p2p_tls_crypto.py -q
```
