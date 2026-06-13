# Pre-flight check for staging/production deployment
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$config = if ($args.Count -gt 0) { $args[0] } else { "node.staging.example.json" }
Write-Host "=== Staging/Prod config check: $config ===" -ForegroundColor Cyan

python -c @"
import json, os, sys
sys.path.insert(0, '.')
from runtime.config import Config

path = sys.argv[1]
cfg = Config.from_json(path)
cfg.apply_env()
errs = cfg.validate()
print(f'mode={cfg.deployment_mode} chain_id={cfg.chain_id} bridge={cfg.bridge_mode}')
if errs:
    print('ISSUES:')
    for e in errs:
        print(f'  - {e}')
    sys.exit(1)
print('OK: config valid')
"@ $config

if ($LASTEXITCODE -ne 0) {
    Write-Host "Fix config before deploy" -ForegroundColor Red
    exit 1
}

Write-Host "Env hints for prod:" -ForegroundColor Gray
Write-Host "  DEPLOYMENT_MODE=prod" -ForegroundColor Gray
Write-Host "  JWT_SECRET=<random>" -ForegroundColor Gray
Write-Host "  RPC_API_KEY_REQUIRED=true" -ForegroundColor Gray
Write-Host "  BRIDGE_MODE=rust (with compiled bridge/abs_bridge_bin)" -ForegroundColor Gray
Write-Host "OK" -ForegroundColor Green
