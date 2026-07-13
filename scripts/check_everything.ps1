# Full local verification for Absolute Blockchain Ultimate.
# Delegates to the unified master script (skips native wheel rebuild for speed).
#
# Usage:
#   .\scripts\check_everything.ps1
#   .\scripts\check_everything.ps1 -Live
#   .\scripts\check_everything.ps1 -Live -P2P
#   .\scripts\check_everything.ps1 -Docker
#
# Full gate with native rebuild (recommended before release):
#   .\scripts\check_hybrid_full.ps1
#   .\scripts\test_blockchain_full.ps1

param(
    [switch]$Live,
    [switch]$P2P,
    [switch]$ProdMesh,
    [switch]$ProdMeshSpawn,
    [switch]$Docker,
    [switch]$DockerBuild,
    [switch]$BuildRust,
    [switch]$NoClean,
    [string]$BaseUrl = "http://127.0.0.1:8080",
    [int]$PytestTimeout = 900,
    [int]$P2PWait = 300,
    [int]$ProdMeshWait = 360,
    [int]$AuditRetries = 1
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$script = Join-Path $ProjectRoot "scripts\test_blockchain_full.ps1"

$args = @("-SkipNativeBuild")
if ($Live) { $args += "-Live" }
if ($P2P) { $args += "-P2P" }
if ($ProdMesh) { $args += "-ProdMesh" }
if ($ProdMeshSpawn) { $args += "-ProdMeshSpawn" }
if ($Docker) { $args += "-Docker" }
if ($DockerBuild) { $args += "-DockerBuild" }
if ($BuildRust) { $args += "-BuildRust" }
if ($NoClean) { $args += "-NoClean" }
$args += @(
    "-BaseUrl", $BaseUrl,
    "-PytestTimeout", "$PytestTimeout",
    "-P2PWait", "$P2PWait",
    "-ProdMeshWait", "$ProdMeshWait",
    "-AuditRetries", "$AuditRetries"
)

powershell -ExecutionPolicy Bypass -File $script @args
exit $LASTEXITCODE
