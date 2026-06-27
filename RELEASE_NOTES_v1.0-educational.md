# Release v1.0-educational

**Educational / experimental only — NOT production.**

## Highlights

- **Single entry point:** `python main.py` (`NodeOrchestrator`)
- **230 REST API endpoints** + JSON-RPC `:8545`
- **Web Explorer:** 31 tabs, 100% API coverage — http://localhost:8080
- **Tokenomics:** 221,000,000 ABS max supply, founder D.U.P. (Uladzimir Dabranski) 17.4%
- **Pool locks:** ecosystem/treasury DAO lock, staking epoch release (32 blocks/epoch)
- **Light client:** SPV + Merkle proofs (17/17 tests pass)
- **Security:** no wallet/private keys in repo; oracle keys from `.env` only
- **Docs:** README, DISCLAIMER, SECURITY, CONTRIBUTING, docs/ARCHITECTURE.md

## Quick start

```bash
git clone https://github.com/Gruver87/absolute-blockchain-ultimate.git
cd absolute-blockchain-ultimate
pip install -r requirements.txt
python main.py
```

## Audit (local)

```bash
python tests/smoke/merkle_light.py
python scripts/final_audit.py
```

## Commits in this release

- `b8771dc` — Unified educational node, docs, tokenomics
- `28a24dc` — Security: remove data/wallet from git, env-only API keys

## License

MIT — see [LICENSE](LICENSE) and [DISCLAIMER.md](DISCLAIMER.md).
