# Release Notes — v1.2.66

## P2P TLS on prod Docker 3-node mesh

Optional encrypted P2P wire for local prod mesh:

```powershell
python scripts/gen_p2p_mesh_tls.py
.\scripts\docker_prod_3node.ps1 -P2pTls
```

- **`scripts/gen_p2p_mesh_tls.py`** — CA + per-node certs in `data/p2p_tls_prod_mesh/`
- **`docker-compose.prod.3node.p2ptls.yml`** — compose overlay (mounts + env)
- **`-P2pTls`** on `docker_prod_3node.ps1` — auto-generate certs, apply overlay, verify `tls.ready` on all nodes

Without `-P2pTls`, behavior is unchanged (plain TCP P2P).

## Verify

```powershell
pytest tests/unit/test_gen_p2p_mesh_tls.py -q
Invoke-RestMethod http://127.0.0.1:18180/p2p/security | Select-Object -ExpandProperty tls
```

See [docs/P2P_TLS.md](docs/P2P_TLS.md).
