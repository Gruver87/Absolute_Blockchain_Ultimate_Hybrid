# Bridge L1 cutover gate — static + optional live checks against running prod node.
param(
    [switch]$Live,
    [string]$BaseUrl = "",
    [switch]$ProbeL1,
    [string]$Config = "node.prod.mainnet-v1.bridge.example.json"
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$dotEnv = Join-Path $ProjectRoot ".env"
if (Test-Path $dotEnv) {
    Get-Content $dotEnv | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) { return }
        $parts = $line.Split("=", 2)
        $key = $parts[0].Trim()
        $val = $parts[1].Trim().Trim('"').Trim("'")
        if ($key) {
            [Environment]::SetEnvironmentVariable($key, $val, "Process")
        }
    }
}

if (-not $BaseUrl) {
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:18080/health/live" -UseBasicParsing -TimeoutSec 3
        if ($resp.StatusCode -eq 200) {
            $BaseUrl = "http://127.0.0.1:18080"
        }
    } catch { }
}

$argsList = @("scripts/bridge_l1_cutover.py", "--config", $Config)
if ($Live) { $argsList += "--live" }
if ($BaseUrl) { $argsList += @("--base-url", $BaseUrl) }
if ($ProbeL1) { $argsList += "--probe-l1" }

python @argsList
exit $LASTEXITCODE
