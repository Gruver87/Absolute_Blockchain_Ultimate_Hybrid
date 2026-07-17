# L1 bridge live probe - static, RPC probe, and optional live node checks.
param(
    [switch]$ProbeL1,
    [switch]$ProbeL1RpcOnly,
    [switch]$Live,
    [switch]$Full,
    [string]$BaseUrl = "",
    [string]$Config = "node.prod.mainnet-v1.bridge.example.json"
)

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
        if ($key) {
            [Environment]::SetEnvironmentVariable($key, $val, "Process")
        }
    }
}

$argsList = @("scripts/bridge_l1_live_probe.py", "--config", $Config)
if ($ProbeL1) { $argsList += "--probe-l1" }
if ($ProbeL1RpcOnly) { $argsList += "--probe-l1-rpc-only" }
if ($Live) { $argsList += "--live" }
if ($Full) { $argsList += "--full" }
if ($BaseUrl) { $argsList += @("--base-url", $BaseUrl) }

python @argsList
exit $LASTEXITCODE
