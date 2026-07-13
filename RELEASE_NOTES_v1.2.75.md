# Release Notes — v1.2.75

## P2P TLS evidence path (prod mesh)

Full workflow on top of v1.2.66 Docker TLS overlay:

```powershell
.\scripts\p2p_tls_evidence_suite.ps1
```

Or step-by-step:

```powershell
python scripts/gen_p2p_mesh_tls.py
.\scripts\docker_prod_3node_p2ptls.ps1 -CeremonyDir data/ceremony_keys
.\scripts\probe_p2p_tls_mesh.ps1 -WaitSec 120
```

Report: `logs/p2p_tls_mesh_verify.json`

## Resilience + failover with TLS

```powershell
.\scripts\prod_mesh_resilience_suite.ps1 -P2pTls -SkipDrRehearsal
.\scripts\p2p_tls_evidence_suite.ps1 -SkipMeshStart -WithFailover
```

## Preflight / monolith

```powershell
.\scripts\prepare_p2p_tls_mesh.ps1
.\scripts\prepare_p2p_tls_mesh.ps1 -Live -WaitSec 60
.\scripts\monolith_gate.ps1 -P2pTlsPreflight -P2pTlsLive
```

## 48h soak (when ready, with TLS mesh)

```powershell
.\scripts\docker_prod_3node.ps1 -P2pTls
.\scripts\prepare_48h_soak.ps1 -RequireP2pTls
```

## Verify

```powershell
pytest tests/unit/test_verify_p2p_tls_mesh.py tests/unit/test_gen_p2p_mesh_tls.py -q
Invoke-RestMethod http://127.0.0.1:18180/p2p/security | Select-Object -ExpandProperty tls
```

See [docs/P2P_TLS.md](docs/P2P_TLS.md).
