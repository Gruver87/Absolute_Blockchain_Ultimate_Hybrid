# Full blockchain verification — delegates to the unified test script.
# Kept for backward compatibility with README/CI references.

param(
    [switch]$Live,
    [switch]$P2P,
    [switch]$Docker,
    [switch]$DockerBuild,
    [switch]$BuildRust,
    [switch]$SkipNativeBuild,
    [switch]$NoClean,
    [string]$BaseUrl = "http://127.0.0.1:8080",
    [int]$PytestTimeout = 900,
    [int]$P2PWait = 300,
    [int]$AuditRetries = 1
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script = Join-Path $ProjectRoot "scripts\test_blockchain_full.ps1"

$args = @()
if ($Live) { $args += "-Live" }
if ($P2P) { $args += "-P2P" }
if ($Docker) { $args += "-Docker" }
if ($DockerBuild) { $args += "-DockerBuild" }
if ($BuildRust) { $args += "-BuildRust" }
if ($SkipNativeBuild) { $args += "-SkipNativeBuild" }
if ($NoClean) { $args += "-NoClean" }
$args += @("-BaseUrl", $BaseUrl, "-PytestTimeout", "$PytestTimeout", "-P2PWait", "$P2PWait", "-AuditRetries", "$AuditRetries")

powershell -ExecutionPolicy Bypass -File $script @args
exit $LASTEXITCODE
