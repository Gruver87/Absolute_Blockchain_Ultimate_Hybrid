# Run operational evidence scripts against live prod mesh (see docs/EVIDENCE_MATRIX.md).
param(
    [switch]$SkipFailover,
    [switch]$SkipSignedTx,
    [switch]$SkipEvm,
    [switch]$RecordEvidence,
    [int]$FailoverWaitSec = 360,
    [string]$GitTag = "v1.2.54"
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

function Get-StepExitCode {
    if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        return [int]$LASTEXITCODE
    }
    if (-not $?) {
        return 1
    }
    return 0
}

function Step([string]$Name, [scriptblock]$Action) {
    Write-Host "`n=== $Name ===" -ForegroundColor Cyan
    & $Action
    $rc = Get-StepExitCode
    if ($rc -ne 0) {
        Write-Host "FAIL: $Name (exit $rc)" -ForegroundColor Red
        if ($RecordEvidence) {
            $tagArg = @()
            if ($GitTag) { $tagArg = @("--git-tag", $GitTag) }
            python (Join-Path $ScriptDir "record_evidence_run.py") --name $Name --result FAIL @tagArg 2>$null | Out-Null
        }
        exit $rc
    }
    Write-Host "OK: $Name" -ForegroundColor Green
    if ($RecordEvidence) {
        $tagArg = @()
        if ($GitTag) { $tagArg = @("--git-tag", $GitTag) }
        python (Join-Path $ScriptDir "record_evidence_run.py") --name $Name --result PASS @tagArg 2>$null | Out-Null
    }
}

Step "mesh stabilize" {
    & (Join-Path $ScriptDir "mesh_stabilize.ps1")
}

Step "mesh health" {
    & (Join-Path $ScriptDir "health_watch.ps1") -ProdMesh -DurationMin 1 -IntervalSec 15
}

if (-not $SkipFailover) {
    Step "failover pre-sync" {
        & (Join-Path $ScriptDir "mesh_stabilize.ps1") -WaitSec 120
    }

    Step "failover drill" {
        & (Join-Path $ScriptDir "prod_mesh_failover.ps1") -WaitSec $FailoverWaitSec
    }
}

if (-not $SkipSignedTx) {
    Step "signed tx smoke" {
        python (Join-Path $ScriptDir "prod_signed_tx_smoke.py")
    }
}

if (-not $SkipEvm) {
    Step "prod EVM smoke" {
        python (Join-Path $ScriptDir "prod_evm_smoke.py")
    }
}

Write-Host "`nOK: prod evidence suite passed" -ForegroundColor Green
Write-Host "  Soak: .\scripts\restart_soak_prod_mesh.ps1 -Hours 48" -ForegroundColor DarkGray
exit 0
