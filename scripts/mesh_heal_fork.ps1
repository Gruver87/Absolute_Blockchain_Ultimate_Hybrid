# Reseed node1 chainstore from node2 when prod mesh forked (node1 ahead on divergent tip).
param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

$node1 = "abs-prod-mesh3-node1-1"
$volFrom = "abs-prod-mesh3_abs-prod-mesh2-data"
$volTo = "abs-prod-mesh3_abs-prod-mesh1-data"

Write-Host "Mesh fork heal: clone node2 chainstore -> node1" -ForegroundColor Yellow
Write-Host "  from volume: $volFrom"
Write-Host "  to volume:   $volTo"
if (-not $Force) {
    Write-Host "Re-run with -Force to apply." -ForegroundColor Cyan
    exit 1
}

docker stop $node1
docker run --rm `
    -v "${volFrom}:/from" `
    -v "${volTo}:/to" `
    alpine:3.20 sh -c "set -e; test -d /from/chainstore; rm -rf /to/chainstore; cp -a /from/chainstore /to/; echo OK: chainstore cloned"

Write-Host "Rebuilding prod image..." -ForegroundColor Cyan
docker compose -f docker-compose.prod.3node.yml -p abs-prod-mesh3 build
docker compose -f docker-compose.prod.3node.yml -p abs-prod-mesh3 up -d --force-recreate
Start-Sleep -Seconds 45
& (Join-Path $ScriptDir "mesh_stabilize.ps1") -WaitSec 120
exit $LASTEXITCODE
