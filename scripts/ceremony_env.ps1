# Shared helpers: persist ceremony deploy env into .env (never commit .env).

function Set-DotEnvKey {
    param(
        [string]$Path,
        [string]$Key,
        [string]$Value
    )
    if (-not $Path -or -not $Key) { return }
    $lines = @()
    if (Test-Path $Path) {
        $lines = @(Get-Content $Path)
    }
    $pattern = "^\s*$([regex]::Escape($Key))\s*="
    $found = $false
    $out = @()
    foreach ($line in $lines) {
        if ($line -match $pattern) {
            $found = $true
            $out += "$Key=$Value"
        } else {
            $out += $line
        }
    }
    if (-not $found) {
        if ($out.Count -gt 0 -and $out[-1].Trim() -ne "") {
            $out += ""
        }
        $out += "$Key=$Value"
    }
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllLines($Path, [string[]]$out, $utf8NoBom)
}

function Sync-CeremonyDeployEnv {
    param(
        [string]$ProjectRoot = "",
        [string]$CeremonyHash = "",
        [string]$ManifestPath = "data/validators.manifest.json"
    )
    if (-not $ProjectRoot) {
        $ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
    }
    $dotEnv = Join-Path $ProjectRoot ".env"
    if (-not (Test-Path $dotEnv)) { return }
    Set-DotEnvKey -Path $dotEnv -Key "VALIDATORS_MANIFEST_PATH" -Value $ManifestPath
    if ($CeremonyHash) {
        Set-DotEnvKey -Path $dotEnv -Key "GENESIS_CEREMONY_HASH" -Value $CeremonyHash
    }
}
