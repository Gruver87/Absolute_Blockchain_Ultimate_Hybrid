# Локальный тест автопоста (без отправки)
param(
    [ValidateSet("scheduled", "release", "both")]
    [string]$Mode = "scheduled",
    [switch]$Send
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)=(.*)$') {
            $k = $matches[1].Trim()
            $v = $matches[2].Trim().Trim('"')
            if ($k -and -not [Environment]::GetEnvironmentVariable($k)) {
                [Environment]::SetEnvironmentVariable($k, $v, "Process")
            }
        }
    }
}

$args = @("scripts/community_autopost.py", "--mode", $Mode)
if (-not $Send) { $args += "--dry-run" }

python @args

if (-not $Send) {
    Write-Host ""
    Write-Host "Dry-run only. To send: .\scripts\run_community_autopost.ps1 -Mode scheduled -Send" -ForegroundColor Yellow
    Write-Host "Requires TELEGRAM_BOT_TOKEN + TELEGRAM_CHANNEL_ID in .env" -ForegroundColor Gray
}
