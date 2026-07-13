# Bridge L1 cutover evidence path (RPC-only pre-deploy, or full after L1 contracts).
param(
    [switch]$RpcOnly,
    [switch]$Full,
    [switch]$Live,
    [string]$BaseUrl = "",
    [string]$Config = "node.prod.mainnet-v1.bridge.example.json"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

$dotEnv = Join-Path $Root ".env"
if (Test-Path $dotEnv) {
    Get-Content $dotEnv | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) { return }
        $parts = $line.Split("=", 2)
        $key = $parts[0].Trim()
        $val = $parts[1].Trim().Trim('"').Trim("'")
        if ($key) { [Environment]::SetEnvironmentVariable($key, $val, "Process") }
    }
}

$bridgeExample = Join-Path $Root ".env.bridge.cutover.example"
if (-not (Test-Path $dotEnv) -and (Test-Path $bridgeExample)) {
    Write-Host "WARN: no .env — copy .env.bridge.cutover.example and set ETH_RPC_URL" -ForegroundColor Yellow
}

$gitTag = "unknown"
try {
    $desc = git describe --tags --abbrev=0 2>$null
    if ($desc) { $gitTag = $desc.Trim() }
} catch { }

$probeL1 = $Full
$probeL1RpcOnly = $RpcOnly -or (-not $Full)
if ($Full) { $probeL1RpcOnly = $false }

function Step([string]$Name, [scriptblock]$Action) {
    Write-Host "`n=== $Name ===" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAIL: $Name" -ForegroundColor Red
        exit $LASTEXITCODE
    }
    Write-Host "OK: $Name" -ForegroundColor Green
}

Step "bridge_l1_live_probe" {
    $probeArgs = @("scripts/bridge_l1_live_probe.py", "--config", $Config)
    if ($probeL1) { $probeArgs += "--probe-l1" }
    elseif ($probeL1RpcOnly) { $probeArgs += "--probe-l1-rpc-only" }
    if ($Live -or $Full) { $probeArgs += "--live" }
    if ($BaseUrl) { $probeArgs += @("--base-url", $BaseUrl) }
    python @probeArgs
}

Step "bridge_l1_cutover_gate" {
    $cutArgs = @("scripts/bridge_l1_cutover.py", "--config", $Config)
    if ($probeL1) { $cutArgs += "--probe-l1" }
    elseif ($probeL1RpcOnly) { $cutArgs += "--probe-l1-rpc-only" }
    if ($Live -or $Full) { $cutArgs += "--live" }
    if ($BaseUrl) { $cutArgs += @("--base-url", $BaseUrl) }
    python @cutArgs
}

Step "mainnet_readiness_bridge_cutover" {
    $mrArgs = @(
        "scripts/mainnet_readiness.py",
        "--bridge-cutover",
        "--no-strict-audit"
    )
    if ($probeL1) { $mrArgs += "--probe-l1" }
    elseif ($probeL1RpcOnly) { $mrArgs += "--probe-l1-rpc-only" }
    if ($Live -or $Full) { $mrArgs += "--bridge-live" }
    python @mrArgs
}

Step "industrial_gate_bridge_cutover" {
    $igArgs = @("scripts/industrial_gate.py", "--bridge-cutover")
    if ($probeL1) { $igArgs += "--probe-l1" }
    elseif ($probeL1RpcOnly) { $igArgs += "--probe-l1-rpc-only" }
    if ($Live -or $Full) { $igArgs += "--bridge-live" }
    python @igArgs
}

$mode = if ($Full) { "full" } elseif ($probeL1) { "probe-l1" } else { "probe-l1-rpc-only" }
python (Join-Path $ScriptDir "record_evidence_run.py") `
    --name "bridge_l1_cutover_$mode" `
    --result PASS `
    --command ".\scripts\bridge_cutover_evidence_suite.ps1" `
    --artifact "logs/bridge_l1_live_probe.json" `
    --git-tag $gitTag `
    2>$null | Out-Null

Write-Host "`nOK: bridge cutover evidence suite passed ($mode)" -ForegroundColor Green
Write-Host "  Before L1 deploy: -RpcOnly (default)" -ForegroundColor DarkGray
Write-Host "  After L1 deploy:  -Full -Live" -ForegroundColor DarkGray
exit 0
