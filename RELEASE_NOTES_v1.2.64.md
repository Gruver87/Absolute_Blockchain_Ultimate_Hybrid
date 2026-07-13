# Release Notes — v1.2.64

## Optional P2P wire TLS (foundation)

Mainnet/public mesh can encrypt the **P2P port** (not just HTTP via nginx):

- Set `P2P_TLS_ENABLED=true` + cert/key/CA paths
- Optional mTLS: `P2P_TLS_REQUIRE_CLIENT_CERT=true`
- Misconfigured TLS **blocks P2P start** (fail closed)
- `/p2p/security.tls` reports readiness

## Dev certs

```bash
python scripts/gen_p2p_dev_tls.py --out-dir data/p2p_tls_dev --node-id dev-node-1
```

See [docs/P2P_TLS.md](docs/P2P_TLS.md).

## Verify

```powershell
pytest tests/unit/test_p2p_tls.py tests/unit/test_p2p_industrial.py -q
python scripts/industrial_gate.py
```
