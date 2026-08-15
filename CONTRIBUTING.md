# Contributing — Absolute Blockchain Ultimate Hybrid

Thank you. This is a **production-hardened R&D / devnet** stack (local prod-mesh evidence). It is **not** a launched public mainnet.

R&D for rust-libp2p / Long-Range / EVM depth lives in [`Gruver87/experimental`](https://github.com/Gruver87/experimental). Do **not** port those kernels onto this audit pin.

## Before you start

1. **30 seconds:** [docs/AT_A_GLANCE.md](docs/AT_A_GLANCE.md) — what is proven vs not.
2. [DISCLAIMER.md](DISCLAIMER.md) — this is **not** a launched public audited mainnet.
3. Run: `python main.py` (not `_archive/`).

## 60-second setup

```bash
git clone https://github.com/Gruver87/Absolute_Blockchain_Ultimate_Hybrid.git
cd Absolute_Blockchain_Ultimate_Hybrid
pip install -r requirements.txt && cp .env.example .env
# Linux/macOS:  make build && make test-quick && python main.py
# Windows:      .\scripts\build_native.ps1 ; .\scripts\check_all.ps1 ; python main.py
```

http://localhost:8080

## How to help

| Action | Why |
|--------|-----|
| Star / Watch Releases | Repo visibility |
| Issues + evidence | Bugs with `data/check_all.json` / soak artifacts |
| Docs / PR | Fixes and tests → **`master`** |

## Branches

| Branch | Role |
|--------|------|
| **`master`** | Default development |
| **`main`** | Mirror of `master` (CI sync) |

PR → **`master`**. We do not invent a fake “team PR” history for hiring optics.

## Development

```bash
git checkout -b feature/my-change
# ... edits ...
pytest tests/ -q
python tests/smoke/merkle_light.py
python scripts/final_audit.py
git commit -m "feat: description"
git push origin feature/my-change
```

Open a Pull Request on GitHub against **`master`**.

## Code style

- Minimal diff — do not refactor unrelated code
- Match neighboring files
- Comments only for non-obvious logic
- Do not commit: `.env`, `data/`, keys, `__pycache__`

## Commit messages

```
feat: add SPV endpoint for block proofs
fix: pool lock check in mempool
docs: update README tokenomics section
test: merkle light client cases
```

## Ideas for contributors

- P2P and sync between nodes
- More pytest coverage instead of script-style tests
- Production-hardening and security gates
- Documentation (English)
- CI: `pytest tests/`, `tests/smoke/merkle_light.py`, `scripts/final_audit.py`

## Questions

- Issues: https://github.com/Gruver87/Absolute_Blockchain_Ultimate_Hybrid/issues
- Author: [@Gruver87](https://github.com/Gruver87)

Thank you for keeping Absolute Blockchain Ultimate honest — green gates are not public mainnet.
