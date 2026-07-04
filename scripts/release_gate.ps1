# Release gate — full blockchain verification before tag/push.
# Same as test_all with native build skipped when wheel already installed.
param(
    [switch]$FullNativeBuild
)

$args = @("-SkipNativeBuild")
if ($FullNativeBuild) {
    $args = @()
}
& "$PSScriptRoot\test_all.ps1" @args
exit $LASTEXITCODE
