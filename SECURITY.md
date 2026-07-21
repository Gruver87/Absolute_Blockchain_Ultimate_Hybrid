# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| `v1.2.x` on `master` | Yes (best-effort R&D) |
| Older tags | Limited — prefer latest release |

This project is a **production-hardened R&D / devnet** stack. It is **not** a launched public mainnet and has **not** completed an independent external security audit.

## Reporting a vulnerability

1. **Do not** open a public issue with exploit details that could harm operators.
2. Prefer a private GitHub Security Advisory (if enabled) or contact the repository owner **Gruver87** via GitHub.
3. Include: affected version/tag, reproduction steps, impact, and whether a fix is proposed.

## Secrets — what must never enter Git

- `data/wallet.json` — use `wallet.example.json`
- `.env` — API keys, JWT, bot tokens, RPC secrets
- `*.db`, `data/` — chain databases
- Private keys, seed phrases, passwords, TLS key material

## What is public in-repo

- `wallet.example.json`, `.env.example`
- Founder **public** address in `runtime/tokenomics.py` (not a private key)

## Cryptography

Transaction ECDSA uses **`cryptography`** (OpenSSL), not `python-ecdsa` (CVE-2024-23342 / Minerva).

Production profile requires Rust/PyO3 `abs_native` (`ABS_REQUIRE_NATIVE_CRYPTO=true`).

## Admin JWT (production)

`GET /auth/token` is **disabled** in prod. Mint an admin token from `JWT_SECRET`:

```bash
python scripts/mint_admin_jwt.py --address ops-admin --hours 24
# Authorization: Bearer <token>
```

Protected admin POSTs require JWT claim `role=admin` (user role → 403).

## Pre-push check

```bash
python scripts/check_secrets.py
```

Runs in CI — commits with embedded secrets should fail.

## If a secret was committed

1. Rotate the secret immediately.
2. Purge from git history if it reached a remote.
3. Open a private report with the owner.
