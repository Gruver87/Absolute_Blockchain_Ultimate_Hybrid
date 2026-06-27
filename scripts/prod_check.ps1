# Validate production node config (node.prod.example.json)
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$config = if ($args.Count -gt 0) { $args[0] } else { "node.prod.example.json" }
& (Join-Path $ProjectRoot "scripts\staging_check.ps1") $config
