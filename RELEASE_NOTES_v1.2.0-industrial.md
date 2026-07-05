# Release v1.2.0-industrial

**Hybrid Python + Rust blockchain node** — industrial R&D profile (API waves 37–63).

## Highlights

- Single entry: `python main.py`
- Multi-node Docker: 2 / 3 / 5 validators + prod 3-node mesh (chain 778888 prep)
- P2P: strict `state_root`, fork/slashing CI, recovery gate (Wave 62)
- REST + JSON-RPC + browser explorer (API wave 61)
- Rust/PyO3 `abs_native`: SHA-256, Merkle, state_root, secp256k1, block/tx hash
- Rust bridge path + L1 queue; prod requires real RPC/secrets when enabled
- Fail-closed prod profile: JWT, RPC keys, CORS, native crypto required
- K8s manifests, Prometheus/Grafana stack

## Quality gate

```powershell
.\scripts\check_hybrid_full.ps1
pytest tests/ -q   # 698 passed, 1 skipped (Jul 2026)
```

## Prod profile (preparation — not live mainnet)

```powershell
.\scripts\setup_prod_env.ps1 -EthRpcUrl "https://..."
.\scripts\docker_prod_3node.ps1          # mesh, bridge OFF
.\scripts\docker_prod.ps1 -Bridge        # bridge cutover lab only
```

## Observability

```bash
docker compose -f docker-compose.observability.yml up -d
# Grafana: http://localhost:3000
```

---

*Not a launched public mainnet. See [DISCLAIMER.md](DISCLAIMER.md) and [docs/MAINNET_GAP_ANALYSIS.md](docs/MAINNET_GAP_ANALYSIS.md).*
