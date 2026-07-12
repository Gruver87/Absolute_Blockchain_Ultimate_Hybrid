# Recover prod mesh when mining stalled (heights drift / mempool not clearing).
param(
    [switch]$RestartContainers,
    [switch]$RebuildMesh,
    [switch]$HealFork
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

if ($HealFork) {
    & (Join-Path $ScriptDir "mesh_heal_fork.ps1") -Force
    exit $LASTEXITCODE
}

if ($RebuildMesh) {
    Write-Host "Rebuilding prod mesh (KeepVolumes)..." -ForegroundColor Cyan
    & (Join-Path $ScriptDir "docker_prod_3node.ps1") -SkipBuild -KeepVolumes
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} elseif ($RestartContainers) {
    Write-Host "Restarting prod mesh containers..." -ForegroundColor Cyan
    docker restart abs-prod-mesh3-node1-1 abs-prod-mesh3-node2-1 abs-prod-mesh3-node3-1
    Start-Sleep -Seconds 40
}

& (Join-Path $ScriptDir "mesh_stabilize.ps1") -WaitSec 180
exit $LASTEXITCODE
