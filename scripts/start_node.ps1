# Quick start: unified node (Windows PowerShell 5.1 + pwsh)
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$NodePorts = @(8080, 8545, 5000, 8766)

function Get-PortListeners {
    param([int[]]$Ports)
    $busy = @()
    foreach ($port in $Ports) {
        $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        if ($conns) {
            $owningPid = ($conns | Select-Object -First 1).OwningProcess
            $busy += [PSCustomObject]@{ Port = $port; OwningPid = $owningPid }
        }
    }
    return $busy
}

Write-Host "=== Absolute Blockchain Ultimate ===" -ForegroundColor Cyan
Write-Host "Entry: python main.py" -ForegroundColor Gray
Write-Host "Web:   http://localhost:8080" -ForegroundColor Gray
Write-Host "RPC:   http://localhost:8545" -ForegroundColor Gray
Write-Host ""

$busy = Get-PortListeners -Ports $NodePorts
if ($busy.Count -gt 0) {
    Write-Host "WARNING: ports already in use (another node running?):" -ForegroundColor Yellow
    foreach ($b in $busy) {
        $name = try { (Get-Process -Id $b.OwningPid -ErrorAction Stop).ProcessName } catch { "?" }
        Write-Host ("  :" + $b.Port + " -> PID " + $b.OwningPid + " (" + $name + ")") -ForegroundColor Yellow
    }
    Write-Host ""
    $answer = Read-Host "Stop old node and continue? [Y/n]"
    if ($answer -eq "" -or $answer -match "^[Yy]") {
        & (Join-Path $ProjectRoot "scripts\stop_node.ps1")
        Start-Sleep -Seconds 1
        $busy = Get-PortListeners -Ports $NodePorts
        if ($busy.Count -gt 0) {
            Write-Host "Ports still busy - aborting. Run .\scripts\stop_node.ps1 manually." -ForegroundColor Red
            exit 1
        }
    }
    else {
        Write-Host "Aborted. Stop the old node first: .\scripts\stop_node.ps1" -ForegroundColor Yellow
        exit 1
    }
}

if (-not (Test-Path "data")) {
    New-Item -ItemType Directory -Path "data" | Out-Null
}

Start-Process -FilePath "http://localhost:8080"
python main.py
