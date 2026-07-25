# Release notes — v1.3.65

## L1 security / fail-closed hardening

Closes consensus-identity and silent-fallback gaps found in the industrial scan.

### What shipped

- Attestation: derive address from pubkey and require equality with claimed `validator`
- P2P: reject unauthenticated `validator_register` in prod/staging/`require_native_crypto`
- P2P: reject attestations when verifier is unavailable
- Blockchain: re-raise native apply failures when fail-closed
- Amount: honor `ABS_REQUIRE_NATIVE_CRYPTO` (and legacy `REQUIRE_NATIVE_CRYPTO`)
- Rocks: corrupt account blob → `AccountCorruptError` (not zero balance)
- HTTP/JSON-RPC: body size cap + batch element cap

### Honesty

- Not a public mainnet claim
- Bridge remains OFF on live mesh; semantic bridge proofs are a later wave
- External audit / ceremony pin remain org blockers

### Version

- `node_version`: `1.3.65-industrial`
