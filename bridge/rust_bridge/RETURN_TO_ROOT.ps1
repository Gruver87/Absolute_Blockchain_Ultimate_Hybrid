# After cargo build you may land here — return to project root.
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Root
Write-Host "OK: project root -> $Root" -ForegroundColor Green
Write-Host "  .\scripts\start_two_nodes.ps1" -ForegroundColor Cyan
Write-Host "  python -m pytest tests/ -q" -ForegroundColor Cyan
