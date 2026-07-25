# At a glance

One-screen card for people who do not read long READMEs. Full detail: [README](../README.md) · proof ledger: [EVIDENCE_MATRIX](EVIDENCE_MATRIX.md).

## What this is

Hybrid **Python + Rust** L1 node with prod-profile Docker mesh, RocksDB, REST/JSON-RPC, `abs_native`, EVM path.

## What it is not

Public audited mainnet · listed ABS token · investment product · bridge ON on live mesh.

## Status

| | |
|---|---|
| Tag | **v1.3.138** |
| CI | Ubuntu `test.yml` + docker + security + fuzz |
| 48h soak | **PASS** |
| Self-check | `make test-quick` / `.\scripts\check_all.ps1` |
| Run | `python main.py` → `:8080` |
| Prod mesh | `778888` profile → `:18180–18182` |

## Where code lives

| Path | Role |
|------|------|
| `native/abs_native/` | Rust (look for `Cargo.toml`) |
| `network/` | P2P control plane |
| `scripts/` | Ops gates |
| `Makefile` | Linux/macOS shortcuts |

## Next click

- Gaps to mainnet: [MAINNET_GAP_ANALYSIS](MAINNET_GAP_ANALYSIS.md)
- Commands: [COMMANDS_REFERENCE](COMMANDS_REFERENCE.md)
- Contribute: [CONTRIBUTING](../CONTRIBUTING.md)
