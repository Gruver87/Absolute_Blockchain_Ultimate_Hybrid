# Release notes — v1.3.158

## Summary

**Industrial JWT secret honesty (no simplifications):**

1. **HS256 min 32 bytes** — `JWT_SECRET` shorter than 32 bytes is refused at mint/verify and by prod `Config.validate` (clears PyJWT `InsecureKeyLengthWarning` from short unit fixtures).
2. Unit fixtures + compose placeholders lengthened to >= 32 bytes.

## Changes

- `middleware/jwt_auth.py` — `MIN_HS256_SECRET_BYTES` / `_assert_hs256_secret`
- `runtime/config.py` — prod JWT weak check uses `min_len=32`
- Tests / compose placeholders updated
- `node_version`: `1.3.158-industrial`

## Honesty

- Soft secret-length gate — **not** key rotation ceremony, not public mainnet, not external audit complete

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13158_jwt_hs256_min_secret.py tests/unit/test_api_prod_auth.py tests/unit/test_prod_config.py -q
```
