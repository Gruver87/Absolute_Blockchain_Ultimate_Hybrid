# Prod mesh FULL operational gate — alias for test_blockchain_full -ProdMeshFull.
# Requires live Docker prod mesh on :18180-:18182 (or use -ProdMeshSpawn).
#
#   .\scripts\prod_mesh_full.ps1
#   .\scripts\prod_mesh_full.ps1 -ProdMeshSpawn
#   .\scripts\prod_mesh_full.ps1 -RecordEvidence

param(
    [switch]$ProdMeshSpawn,
    [switch]$RecordEvidence,
    [switch]$SkipNativeBuild,
    [int]$ProdMeshWait = 360,
    [int]$ProdMeshFailoverWait = 360,
    [string]$EvidenceGitTag = "v1.2.54"
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$target = Join-Path $ScriptDir "test_blockchain_full.ps1"

$args = @("-ProdMeshFull")
if ($ProdMeshSpawn) { $args += "-ProdMeshSpawn" }
if ($RecordEvidence) { $args += "-RecordEvidence" }
if ($SkipNativeBuild) { $args += "-SkipNativeBuild" }
$args += @(
    "-ProdMeshWait", "$ProdMeshWait",
    "-ProdMeshFailoverWait", "$ProdMeshFailoverWait",
    "-EvidenceGitTag", $EvidenceGitTag
)

powershell -ExecutionPolicy Bypass -File $target @args
exit $LASTEXITCODE
