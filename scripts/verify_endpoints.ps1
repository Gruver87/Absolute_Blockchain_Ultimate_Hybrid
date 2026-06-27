# Verify key REST endpoints on a running node (step 2 checklist)
$Base = if ($env:ABS_HTTP) { $env:ABS_HTTP } else { "http://127.0.0.1:8080" }

$paths = @(
    "/health/live",
    "/status",
    "/tokenomics",
    "/founder",
    "/allocation",
    "/peers",
    "/bridge",
    "/sync/status",
    "/wallet/status",
    "/mempool",
    "/openapi.json"
)

Write-Host "=== ABS endpoint verification ===" -ForegroundColor Cyan
Write-Host "Base: $Base" -ForegroundColor Gray
Write-Host ""

$failed = 0
foreach ($p in $paths) {
    try {
        $r = Invoke-RestMethod -Uri "$Base$p" -TimeoutSec 8
        Write-Host ("OK  $p") -ForegroundColor Green
    }
    catch {
        Write-Host ("FAIL $p  $($_.Exception.Message)") -ForegroundColor Red
        $failed++
    }
}

if ($failed -gt 0) {
    Write-Host ""
    Write-Host "$failed endpoint(s) failed. Is the node running? .\scripts\start_node.ps1" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "All endpoints OK. Docs: $Base/docs" -ForegroundColor Green
