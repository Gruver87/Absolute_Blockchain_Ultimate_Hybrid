# Release notes — v1.3.69

## Block-scoped sat session + industrial verify script

### What shipped

- Mixed-block native apply: prefetch touched accounts, keep sat session in memory, one `_writeback_accounts_sat` at end
- Avoids per-tx `get_total_supply` scans on the mixed path
- `scripts/verify_industrial_waves.py` (+ `.ps1`) — needles + unit tests + `industrial_gate` for waves 1.3.65–1.3.69

### Honesty

- EVM host still writes code/storage via Python DB during the block
- Session covers fee/nonce/value sat rows, not full opcode-loop Rocks ownership
- Not a public mainnet claim

### Version

- `node_version`: `1.3.69-industrial`

### Verify

```powershell
python scripts/verify_industrial_waves.py
# or
.\scripts\verify_industrial_waves.ps1
```
