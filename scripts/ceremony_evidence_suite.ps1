# Genesis ceremony evidence path (preflight + mainnet readiness + audit sync).
param(
    [string]$CeremonyDir = "data/ceremony_keys",
    [switch]$StrictMainnet,
    [switch]$RequireEnvPin
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

if (Test-Path (Join-Path $Root ".env")) {
    Get-Content (Join-Path $Root ".env") | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)=(.*)$') {
            $k = $matches[1].Trim()
            $v = $matches[2].Trim().Trim([char]34).Trim([char]39)
            if ($k) { Set-Item -Path "env:$k" -Value $v }
        }
    }
}

$gitTag = "unknown"
try {
    $desc = git describe --tags --abbrev=0 2>$null
    if ($desc) { $gitTag = $desc.Trim() }
} catch { }

function Step([string]$Name, [scriptblock]$Action) {
    Write-Host "`n=== $Name ===" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAIL: $Name" -ForegroundColor Red
        exit $LASTEXITCODE
    }
    Write-Host "OK: $Name" -ForegroundColor Green
}

Step "ceremony_preflight" {
    $pfArgs = @("scripts/ceremony_preflight.py", "--ceremony-dir", $CeremonyDir)
    if ($StrictMainnet) { $pfArgs += "--strict-mainnet" }
    if ($RequireEnvPin) { $pfArgs += "--require-env-pin" }
    python @pfArgs
}

Step "mainnet_readiness_ceremony" {
    python scripts/mainnet_readiness.py --ceremony-dir $CeremonyDir --no-strict-audit
}

Step "external_audit_sync" {
    python scripts/external_audit_tracker.py --sync-automated
}

python (Join-Path $ScriptDir "record_evidence_run.py") `
    --name ceremony_preflight_live `
    --result PASS `
    --command ".\scripts\ceremony_evidence_suite.ps1" `
    --artifact "data/ceremony_preflight.json" `
    --git-tag $gitTag `
    2>$null | Out-Null

Write-Host "`nOK: ceremony evidence suite passed" -ForegroundColor Green
Write-Host "  Pin hash: .\scripts\pin_ceremony_hash.ps1 -CeremonyDir $CeremonyDir" -ForegroundColor DarkGray
Write-Host "  Deploy:   .\scripts\deploy_ceremony_prod.ps1 -CeremonyDir $CeremonyDir" -ForegroundColor DarkGray
exit 0
