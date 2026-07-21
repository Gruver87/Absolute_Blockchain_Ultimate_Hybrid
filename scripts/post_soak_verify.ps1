# Post-soak verification — single entry for work after the 48h soak.
#
# Default (use already-installed abs_native wheel):
#   .\scripts\post_soak_verify.ps1
#
# Rebuild native wheel first (recommended if you just pulled):
#   .\scripts\post_soak_verify.ps1 -RebuildNative
#
# Also run Rust clippy -D warnings:
#   .\scripts\post_soak_verify.ps1 -RebuildNative -WithClippy

param(
    [switch]$RebuildNative,
    [switch]$WithClippy
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$argsList = @()
if ($RebuildNative) { $argsList += "--rebuild-native" }
if ($WithClippy) { $argsList += "--with-clippy" }

Write-Host "Running post-soak verify from $Root" -ForegroundColor Cyan
python scripts/post_soak_verify.py @argsList
exit $LASTEXITCODE
