# Quick prod mesh restart without full image rebuild.
param(
    [switch]$KeepData
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$args = @("-SkipBuild")
if ($KeepData) {
    $args += "-KeepVolumes", "-NoCloneDb"
}
& "$ScriptDir\docker_prod_3node.ps1" @args
